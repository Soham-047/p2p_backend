

# # chat/consumers.py

# import json
# import base64
# from django.conf import settings
# from cryptography.fernet import Fernet
# from channels.generic.websocket import AsyncWebsocketConsumer
# from channels.db import database_sync_to_async
# from users.models import CustomUser as User
# from .models import Message

# class ChatConsumer(AsyncWebsocketConsumer):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Initialize Fernet with the key from settings.py
#         self.fernet = Fernet(settings.FERNET_KEY)

#     async def connect(self):
#         self.sender = self.scope['user']
#         # Ensure user is authenticated before connecting
#         if not self.sender.is_authenticated:
#             await self.close()
#             return

#         self.receiver_username = self.scope['url_route']['kwargs']['username']
        
#         # Create a consistent, unique room name for the two users
#         self.room_group_name = (
#             f'private_{min(self.sender.username, self.receiver_username)}'
#             f'_{max(self.sender.username, self.receiver_username)}'
#         )

#         await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#         await self.accept()

#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

#     async def receive(self, text_data):
#         try:
#             data = json.loads(text_data)
#             plain_text_message = data.get('message')
#             receiver_username = data.get('receiver')

#             if not plain_text_message or not receiver_username:
#                 await self.send_error("Invalid payload. 'message' and 'receiver' are required.")
#                 return

#             # Encrypt the plain text message using Fernet
#             encrypted_bytes = self.fernet.encrypt(plain_text_message.encode('utf-8'))
#             ciphertext_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')

#             # Save the encrypted message to the database
#             message_id = await self.save_message(self.sender.username, receiver_username, ciphertext_b64)

#             # Broadcast the encrypted message to the room group
#             await self.channel_layer.group_send(
#                 self.room_group_name,
#                 {
#                     'type': 'chat_message',
#                     'message_id': message_id.id,
#                     'ciphertext': ciphertext_b64,
#                     'sender': self.sender.username,
#                 }
#             )
#         except Exception as e:
#             await self.send_error(f"An error occurred: {str(e)}")

#     async def chat_message(self, event):
#         """
#         Handler for messages broadcasted from the channel layer.
#         Sends the encrypted message to the client.
#         """
#         await self.send(text_data=json.dumps({
#             'message_id': event['message_id'],
#             'ciphertext': event['ciphertext'],
#             'sender': event['sender'],
#         }))
    
#     async def send_error(self, error_message):
#         """
#         Helper function to send a formatted error message to the client.
#         """
#         await self.send(text_data=json.dumps({"error": error_message}))

#     @database_sync_to_async
#     def save_message(self, sender_username, receiver_username, ciphertext_b64):
#         """
#         Saves the message to the database.
#         This runs in a separate thread to avoid blocking the async event loop.
#         """
#         try:
#             sender_obj = User.objects.get(username=sender_username)
#             receiver_obj = User.objects.get(username=receiver_username)
            
#             # The ciphertext in the database should store raw bytes
#             ciphertext_bytes = base64.b64decode(ciphertext_b64)
            
#             return Message.objects.create(
#                 sender=sender_obj,
#                 receiver=receiver_obj,
#                 ciphertext=ciphertext_bytes,
#             )
#         except User.DoesNotExist:
#             # Handle the case where a user might not exist
#             print(f"Error: User '{sender_username}' or '{receiver_username}' not found.")

# from channels.generic.websocket import AsyncWebsocketConsumer
# from channels.db import database_sync_to_async
# from users.models import CustomUser
# import json

# class TestConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         await self.accept()
#         await self.send(text_data=json.dumps({"message": "WebSocket connected!"}))

#     async def disconnect(self, close_code):
#         print(f"Disconnected with code {close_code}")

#     async def receive(self, text_data=None, bytes_data=None):
#         data = json.loads(text_data)
#         await self.send(text_data=json.dumps({"echo": data}))


# chat/consumers.py

import json
import base64
import time
from django.conf import settings
from cryptography.fernet import Fernet
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from users.models import CustomUser as User
from .models import Message
from . import redis_helpers  # <-- Import the redis helpers

class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize Fernet for encryption
        self.fernet = Fernet(settings.FERNET_KEY)
        # Initialize Redis connection
        self.redis_conn = redis_helpers.r()

    async def connect(self):
        self.sender = self.scope['user']
        if not self.sender.is_authenticated:
            await self.close()
            return

        # Fetch the receiver user object and store it
        receiver_username = self.scope['url_route']['kwargs']['username']
        self.receiver = await self.get_user(receiver_username)
        
        if not self.receiver:
            await self.send_error("The user you are trying to chat with does not exist.")
            await self.close()
            return
            
        # Create a consistent room name for Django Channels broadcasting
        # Note: This is separate from our Redis keys
        sorted_usernames = sorted([self.sender.username, self.receiver.username])
        self.room_group_name = f'private_{sorted_usernames[0]}_{sorted_usernames[1]}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # --- REDIS INTEGRATION: Mark messages as read upon connecting ---
        # When a user connects to a chat, clear their unread count from the other user.
        unread_key = redis_helpers.unread_key(self.sender.id)
        self.redis_conn.hdel(unread_key, self.receiver.id)


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            plain_text_message = data.get('message')

            if not plain_text_message:
                await self.send_error("Invalid payload. 'message' field is required.")
                return

            # Encrypt the message for database storage
            encrypted_bytes = self.fernet.encrypt(plain_text_message.encode('utf-8'))
            ciphertext_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')

            # Prepare the message payload for broadcasting and caching
            timestamp = int(time.time())
            message_payload = {
                'sender': self.sender.username,
                'ciphertext': ciphertext_b64,
                'timestamp': timestamp,
            }
            
            # --- REDIS INTEGRATION: Storing and updating chat data ---
            # 1. Add message to the Redis chat history (for fast lookups)
            chat_history_key = redis_helpers.chat_key(self.sender.id, self.receiver.id)
            self.redis_conn.lpush(chat_history_key, json.dumps(message_payload))
            self.redis_conn.ltrim(chat_history_key, 0, 99) # Keep only the latest 100 messages

            # 2. Update recent chats for both users with a new timestamp
            self.redis_conn.zadd(redis_helpers.recent_chats_key(self.sender.id), {self.receiver.id: timestamp})
            self.redis_conn.zadd(redis_helpers.recent_chats_key(self.receiver.id), {self.sender.id: timestamp})
            
            # 3. Increment the unread count for the receiver
            self.redis_conn.hincrby(redis_helpers.unread_key(self.receiver.id), self.sender.id, 1)

            # --- DATABASE PERSISTENCE ---
            # Save the encrypted message to the main database
            message_obj = await self.save_message(self.sender, self.receiver, ciphertext_b64)

            # --- BROADCASTING ---
            # Broadcast the message to the room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': message_obj.id, # Send DB id
                    'ciphertext': ciphertext_b64,
                    'sender': self.sender.username,
                }
            )
        except Exception as e:
            await self.send_error(f"An error occurred: {str(e)}")

    async def chat_message(self, event):
        """
        Handler for messages broadcasted from the channel layer.
        """
        await self.send(text_data=json.dumps({
            'message_id': event['message_id'],
            'ciphertext': event['ciphertext'],
            'sender': event['sender'],
        }))
    
    async def send_error(self, error_message):
        """
        Helper function to send a formatted error message to the client.
        """
        await self.send(text_data=json.dumps({"error": error_message}))

    @database_sync_to_async
    def get_user(self, username):
        """Fetches a user from the database asynchronously."""
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, sender_obj, receiver_obj, ciphertext_b64):
        """
        Saves the message to the database.
        """
        # The ciphertext in the database should store raw bytes
        ciphertext_bytes = base64.b64decode(ciphertext_b64)
        
        return Message.objects.create(
            sender=sender_obj,
            receiver=receiver_obj,
            ciphertext=ciphertext_bytes,
        )