# import json
# import base64
# from channels.generic.websocket import AsyncWebsocketConsumer
# from channels.db import database_sync_to_async
# from users.models import CustomUser as User
# from .models import Message

# class ChatConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         self.sender = self.scope['user']
#         self.receiver_username = self.scope['url_route']['kwargs']['username']

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
#             ciphertext_b64 = data.get('ciphertext')
#             receiver_username = data.get('receiver')

#             if not ciphertext_b64 or not receiver_username:
#                 await self.send(text_data=json.dumps({"error": "Invalid payload"}))
#                 return

#             # validate base64
#             try:
#                 base64.b64decode(ciphertext_b64)
#             except Exception:
#                 await self.send(text_data=json.dumps({"error": "Invalid ciphertext"}))
#                 return

#             await self.save_message(self.sender.username, receiver_username, ciphertext_b64)

#             await self.channel_layer.group_send(
#                 self.room_group_name,
#                 {
#                     'type': 'chat_message',
#                     'ciphertext': ciphertext_b64,
#                     'sender': self.sender.username,
#                 }
#             )
#         except Exception as e:
#             await self.send(text_data=json.dumps({"error": str(e)}))


#     async def chat_message(self, event):
#         await self.send(text_data=json.dumps({
#             'ciphertext': event['ciphertext'],
#             'sender': event['sender'],
#         }))

#     @database_sync_to_async
#     def save_message(self, sender, receiver, ciphertext_b64):
#         sender_obj = User.objects.get(username=sender)
#         receiver_obj = User.objects.get(username=receiver)
#         ciphertext_bytes = base64.b64decode(ciphertext_b64)
#         Message.objects.create(
#             sender=sender_obj,
#             receiver=receiver_obj,
#             ciphertext=ciphertext_bytes,
#         )



# chat/consumers.py

import json
import base64
from django.conf import settings
from cryptography.fernet import Fernet
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from users.models import CustomUser as User
from .models import Message

class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize Fernet with the key from settings.py
        self.fernet = Fernet(settings.FERNET_KEY)

    async def connect(self):
        self.sender = self.scope['user']
        # Ensure user is authenticated before connecting
        if not self.sender.is_authenticated:
            await self.close()
            return

        self.receiver_username = self.scope['url_route']['kwargs']['username']
        
        # Create a consistent, unique room name for the two users
        self.room_group_name = (
            f'private_{min(self.sender.username, self.receiver_username)}'
            f'_{max(self.sender.username, self.receiver_username)}'
        )

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            plain_text_message = data.get('message')
            receiver_username = data.get('receiver')

            if not plain_text_message or not receiver_username:
                await self.send_error("Invalid payload. 'message' and 'receiver' are required.")
                return

            # Encrypt the plain text message using Fernet
            encrypted_bytes = self.fernet.encrypt(plain_text_message.encode('utf-8'))
            ciphertext_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')

            # Save the encrypted message to the database
            message_id = await self.save_message(self.sender.username, receiver_username, ciphertext_b64)

            # Broadcast the encrypted message to the room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': message_id.id,
                    'ciphertext': ciphertext_b64,
                    'sender': self.sender.username,
                }
            )
        except Exception as e:
            await self.send_error(f"An error occurred: {str(e)}")

    async def chat_message(self, event):
        """
        Handler for messages broadcasted from the channel layer.
        Sends the encrypted message to the client.
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
    def save_message(self, sender_username, receiver_username, ciphertext_b64):
        """
        Saves the message to the database.
        This runs in a separate thread to avoid blocking the async event loop.
        """
        try:
            sender_obj = User.objects.get(username=sender_username)
            receiver_obj = User.objects.get(username=receiver_username)
            
            # The ciphertext in the database should store raw bytes
            ciphertext_bytes = base64.b64decode(ciphertext_b64)
            
            return Message.objects.create(
                sender=sender_obj,
                receiver=receiver_obj,
                ciphertext=ciphertext_bytes,
            )
        except User.DoesNotExist:
            # Handle the case where a user might not exist
            print(f"Error: User '{sender_username}' or '{receiver_username}' not found.")