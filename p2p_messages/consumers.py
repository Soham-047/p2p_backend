

# from datetime import datetime
# from datetime import timezone
# # import timezone
# import json
# import base64
# import time
# import logging
# from django.conf import settings
# from cryptography.fernet import Fernet
# from channels.generic.websocket import AsyncWebsocketConsumer
# from channels.db import database_sync_to_async
# from users.models import CustomUser as User
# from .models import Message
# from . import redis_helpers

# logger = logging.getLogger(__name__)  # <-- logger


# class ChatConsumer(AsyncWebsocketConsumer):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fernet = Fernet(settings.FERNET_KEY)
#         self.redis_conn = redis_helpers.r()
#         self.room_group_name = None   # <-- always defined

#     async def connect(self):
#         self.sender = self.scope['user']
#         if not self.sender.is_authenticated:
#             await self.accept()  # accept first
#             await self.send_error("Authentication failed. Closing connection.")
#             await self.close()
#             return


#         receiver_username = self.scope['url_route']['kwargs']['username']
#         self.receiver = await self.get_user(receiver_username)
        
#         if not self.receiver:
#             await self.send_error(f"Receiver '{receiver_username}' not found. Closing connection.")
#             logger.error(f"Chat connect failed: receiver '{receiver_username}' not found.")
#             await self.close()
#             return

#         sorted_usernames = sorted([self.sender.username, self.receiver.username])
#         self.room_group_name = f'private_{sorted_usernames[0]}_{sorted_usernames[1]}'

#         await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#         await self.accept()

#         # Mark messages as read
#         unread_key = redis_helpers.unread_key(self.sender.id)
#         self.redis_conn.hdel(unread_key, self.receiver.id)

#     async def disconnect(self, close_code):
#         if self.room_group_name:  # <-- safe guard
#             await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
#         logger.info(f"WebSocket disconnected (user={self.sender}, code={close_code})")

#     async def receive(self, text_data):
#         try:
#             data = json.loads(text_data)
#             plain_text_message = data.get('message')

#             if not plain_text_message:
#                 await self.send_error("Invalid payload. 'message' field is required.")
#                 return

#             encrypted_bytes = self.fernet.encrypt(plain_text_message.encode('utf-8'))
#             ciphertext_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')

#             # timestamp = int(time.time())
#             # timestamp = datetime.now(timezone.utc).isoformat()
#             # ISO for payload
#             timestamp_iso = datetime.now(timezone.utc).isoformat()

#             # Epoch for Redis ZADD
#             timestamp_epoch = datetime.now(timezone.utc).timestamp()
#             message_payload = {
#                 'sender': self.sender.username,
#                 'ciphertext': ciphertext_b64,
#                 'timestamp': timestamp_iso,
#             }

#             # Redis cache updates
#             chat_history_key = redis_helpers.chat_key(self.sender.id, self.receiver.id)
#             self.redis_conn.lpush(chat_history_key, json.dumps(message_payload))
#             self.redis_conn.ltrim(chat_history_key, 0, 99)

#             self.redis_conn.zadd(redis_helpers.recent_chats_key(self.sender.id), {self.receiver.id: timestamp_epoch})
#             self.redis_conn.zadd(redis_helpers.recent_chats_key(self.receiver.id), {self.sender.id: timestamp_epoch})
#             self.redis_conn.hincrby(redis_helpers.unread_key(self.receiver.id), self.sender.id, 1)

#             # Save to DB
#             message_obj = await self.save_message(self.sender, self.receiver, ciphertext_b64)

#             # Broadcast
#             await self.channel_layer.group_send(
#                 self.room_group_name,
#                 {
#                     'type': 'chat_message',
#                     'message_id': message_obj.id,
#                     'ciphertext': ciphertext_b64,
#                     'sender': self.sender.username,
#                 }
#             )
#         except Exception as e:
#             logger.exception("Error in receive()")
#             await self.send_error(f"An error occurred: {str(e)}")

#     async def chat_message(self, event):
#         await self.send(text_data=json.dumps({
#             'message_id': event['message_id'],
#             'ciphertext': event['ciphertext'],
#             'sender': event['sender'],
#         }))

#     async def send_error(self, error_message):
#         await self.send(text_data=json.dumps({"error": error_message}))

#     @database_sync_to_async
#     def get_user(self, username):
#         try:
#             return User.objects.get(username=username)
#         except User.DoesNotExist:
#             return None

#     @database_sync_to_async
#     def save_message(self, sender_obj, receiver_obj, ciphertext_b64):
#         ciphertext_bytes = base64.b64decode(ciphertext_b64)
#         return Message.objects.create(
#             sender=sender_obj,
#             receiver=receiver_obj,
#             ciphertext=ciphertext_bytes,
#         )







# chat/consumers.py

# 1. IMPORT THE ASYNC VERSION OF THE REDIS LIBRARY
import redis.asyncio as redis 
from datetime import datetime, timezone
import json
import base64
import logging
from django.conf import settings
from cryptography.fernet import Fernet
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from users.models import CustomUser as User
from .models import Message
from . import redis_helpers

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fernet = Fernet(settings.FERNET_KEY)
        self.room_group_name = None
        # DO NOT create the connection here in the sync __init__
        self.redis_conn = None 

    async def user_online_status(self, event):
        """
        Handles the 'user_online_status' event from the channel layer.
        """
        # Forward the online status update to the client (browser).
        await self.send(text_data=json.dumps({
            'type': 'online_status_update', # This is the type your JS will look for
            'user_id': event['user_id'],
            'is_online': event['is_online']
        }))

    async def connect(self):
        # 2. ESTABLISH THE ASYNC CONNECTION HERE
        try:
            self.redis_conn = await redis.from_url(settings.REDIS_URL)
            is_connected = await self.redis_conn.ping()
            if not is_connected:
                logger.error("!!! REDIS PING FAILED in connect !!!")
                await self.close(); return
            logger.info("+++ Redis connection successful in connect +++")
        except Exception as e:
            logger.exception("!!! FAILED to connect to Redis in connect !!!")
            await self.close(); return
        



        self.sender = self.scope['user']
        if not self.sender.is_authenticated:
            await self.accept()
            await self.send_error("Authentication failed. Closing connection.")
            await self.close()
            return

        receiver_username = self.scope['url_route']['kwargs']['username']
        self.receiver = await self.get_user(receiver_username)
        
        if not self.receiver:
            await self.send_error(f"Receiver '{receiver_username}' not found.")
            await self.close()
            return

        sorted_usernames = sorted([self.sender.username, self.receiver.username])
        self.room_group_name = f'private_{sorted_usernames[0]}_{sorted_usernames[1]}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        if self.room_group_name:
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "user_online_status", "user_id": self.receiver.username, "is_online": True}
            )
        # Mark messages as read, now with await
        unread_key = redis_helpers.unread_key(self.sender.id)
        # 3. AWAIT EVERY REDIS COMMAND
        await self.redis_conn.hdel(unread_key, self.receiver.id)

    # async def disconnect(self, close_code):
    #     # if self.room_group_name:
    #     #     await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        
    #     # # Gracefully close the Redis connection
    #     # if self.redis_conn:
    #     #     await self.redis_conn.close()
            
    #     # logger.info(f"WebSocket disconnected (user={self.sender}, code={close_code})")

    #     if self.room_group_name:
    #         await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
    #     if self.redis_conn:
    #         await self.redis_conn.close()
    #     logger.info("WebSocket disconnected")

    # chat/consumers.py

    async def disconnect(self, close_code):
        # This method is AUTOMATICALLY called by the server in BOTH cases 
        # (clean and unclean disconnections).
        
        # Remove user from the online set in Redis
        try:
            await self.redis_conn.srem("online_users", self.sender.id)
            logger.info(f"User {self.sender.id} disconnected and was removed from online_users set.")
        except Exception as e:
            logger.error(f"Failed to remove user {self.sender.id} from online set: {e}")

        # Broadcast to the room that this user is now offline
        if self.room_group_name:
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "user_online_status", "user_id": self.sender.username, "is_online": False}
            )


    # async def receive(self, text_data):
    #     try:
    #         data = json.loads(text_data)
    #         plain_text_message = data.get('message')

    #         if not plain_text_message:
    #             await self.send_error("Invalid payload. 'message' field is required.")
    #             return

    #         encrypted_bytes = self.fernet.encrypt(plain_text_message.encode('utf-8'))
    #         ciphertext_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')
            
    #         timestamp_iso = datetime.now(timezone.utc).isoformat()
    #         timestamp_epoch = datetime.now(timezone.utc).timestamp()

    #         message_payload = {
    #             'sender': self.sender.username,
    #             'ciphertext': ciphertext_b64,
    #             'timestamp': timestamp_iso,
    #         }

    #         # 3. AWAIT EVERY REDIS COMMAND
    #         chat_history_key = redis_helpers.chat_key(self.sender.id, self.receiver.id)
    #         await self.redis_conn.lpush(chat_history_key, json.dumps(message_payload))
    #         await self.redis_conn.ltrim(chat_history_key, 0, 99)

    #         await self.redis_conn.zadd(redis_helpers.recent_chats_key(self.sender.id), {self.receiver.id: timestamp_epoch})
    #         await self.redis_conn.zadd(redis_helpers.recent_chats_key(self.receiver.id), {self.sender.id: timestamp_epoch})
    #         await self.redis_conn.hincrby(redis_helpers.unread_key(self.receiver.id), self.sender.id, 1)

    #         # Save to DB
    #         message_obj = await self.save_message(self.sender, self.receiver, ciphertext_b64)

    #         # Broadcast
    #         await self.channel_layer.group_send(
    #             self.room_group_name,
    #             {
    #                 'type': 'chat_message',
    #                 'message_id': message_obj.id,
    #                 'ciphertext': ciphertext_b64,
    #                 'sender': self.sender.username,
    #             }
    #         )
    #     except Exception as e:
    #         logger.exception("Error in receive()")
    #         await self.send_error(f"An error occurred: {str(e)}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            plain_text_message = data.get('message')

            if not plain_text_message:
                await self.send_error("Invalid payload. 'message' field is required.")
                return

            # --- Step 1: Encrypt and Save to Database FIRST ---
            # This gets us the final message ID and timestamp for the cache.
            encrypted_bytes = self.fernet.encrypt(plain_text_message.encode('utf-8'))
            ciphertext_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')
            message_obj = await self.save_message(self.sender, self.receiver, ciphertext_b64)

            # --- Step 2: Create the CONSISTENT payload for Redis ---
            # This structure now perfectly matches what your API view expects.
            message_payload = {
                "id": message_obj.id,
                "sender_id": self.sender.id, # Using the sender's ID
                "ciphertext": ciphertext_b64,
                "timestamp": message_obj.timestamp.isoformat(),
            }

            # --- Step 3: Update Redis Cache (with logging) ---
            chat_history_key = redis_helpers.chat_key(self.sender.id, self.receiver.id)
            timestamp_epoch = message_obj.timestamp.timestamp()

            logger.info(f"Attempting to LPUSH to Redis key: {chat_history_key}")
            list_length = await self.redis_conn.lpush(chat_history_key, json.dumps(message_payload))
            logger.info(f"+++ LPUSH successful. New list length for key is: {list_length} +++")

            await self.redis_conn.ltrim(chat_history_key, 0, 99)
            await self.redis_conn.zadd(redis_helpers.recent_chats_key(self.sender.id), {self.receiver.id: timestamp_epoch})
            await self.redis_conn.zadd(redis_helpers.recent_chats_key(self.receiver.id), {self.sender.id: timestamp_epoch})
            await self.redis_conn.hincrby(redis_helpers.unread_key(self.receiver.id), self.sender.id, 1)

            # --- Step 4: Broadcast to the Channel Layer ---
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': message_obj.id,
                    'ciphertext': ciphertext_b64,
                    'sender': self.sender.username,
                }
            )
        except Exception as e:
            # Log the full traceback for better debugging
            logger.exception("!!! An error occurred in receive() !!!")
            await self.send_error(f"An error occurred: {str(e)}")
    # ... (the rest of your methods like chat_message, save_message, etc., remain the same) ...
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message_id': event['message_id'],
            'ciphertext': event['ciphertext'],
            'sender': event['sender'],
        }))

    async def send_error(self, error_message):
        await self.send(text_data=json.dumps({"error": error_message}))

    @database_sync_to_async
    def get_user(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, sender_obj, receiver_obj, ciphertext_b64):
        ciphertext_bytes = base64.b64decode(ciphertext_b64)
        return Message.objects.create(
            sender=sender_obj,
            receiver=receiver_obj,
            ciphertext=ciphertext_bytes,
        )