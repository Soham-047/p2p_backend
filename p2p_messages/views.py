# Standard Library
import json

# Third-Party
from cryptography.fernet import Fernet, InvalidToken
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.dateparse import parse_datetime
# Django
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import Q, F as DjF, Case, When, IntegerField

from django.db.models.functions import Greatest, Least
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

# Local Apps
from users.models import CustomUser as User
from .models import Message
from .serializers import (
    MessageSerializer,
    MessageDecryptSerializer,
    RecentChatSerializer,
)
from .redis_helpers import r, chat_key, recent_chats_key, unread_key
from .tasks import (
    invalidate_recent_chats_cache,
    increment_unread_counter,
    send_realtime_notification,
)


# --------------------------
# Create + List Messages
# --------------------------
# class MessageListCreateAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = MessageSerializer(data=request.data)
#         if serializer.is_valid():
#             msg = serializer.save(sender=request.user)

#             # Async tasks
#             invalidate_recent_chats_cache.delay(request.user.id, msg.receiver_id)
#             increment_unread_counter.delay(msg.receiver_id, msg.sender_id)

#             payload = {
#                 "id": msg.id,
#                 "sender": msg.sender.username,
#                 "receiver": msg.receiver.username,
#                 "timestamp": msg.timestamp.isoformat(),
#             }
#             send_realtime_notification.delay(msg.receiver_id, payload)

#             return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def get(self, request):
#         user = request.user
#         messages = Message.objects.filter(Q(sender=user) | Q(receiver=user)).order_by('-timestamp')
#         serializer = MessageSerializer(messages, many=True)
#         return Response(serializer.data)
from drf_spectacular.utils import *
import sys
class MessageListCreateAPIView(APIView):
    """
    Handles the creation of a new message.
    The GET method for listing all messages has been removed in favor of the more
    specific and performant ChatHistoryView and RecentChatsAPIView.
    """
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="Create a new message",
        description="Create a new message between two users.",
        request=MessageSerializer,
        responses={
            201: MessageSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
        tags=["Messages"],
    )


    def post(self, request):
        print(f"Received ciphertext: '{request.data.get('ciphertext')}'", file=sys.stderr)
        serializer = MessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # 1. Save to the main database (source of truth)
        msg = serializer.save(sender=request.user)

        # 2. Proactively update Redis cache for immediate access
        redis_conn = r()
        message_payload = {
            "id": msg.id,
            "sender_id": msg.sender.id,
            # "ciphertext": msg.ciphertext.decode('latin1'),
            "ciphertext": base64.b64encode(bytes(msg.ciphertext)).decode('utf-8'), 
            "timestamp": msg.timestamp.isoformat(),
        }
        
        # Push to the chat history list and keep it trimmed
        key = chat_key(msg.sender_id, msg.receiver_id)
        redis_conn.lpush(key, json.dumps(message_payload))
        redis_conn.ltrim(key, 0, 99) # Keep the latest 100 messages

        # 3. Update recent chats sorted set and unread counts in Redis
        timestamp = int(msg.timestamp.timestamp())
        redis_conn.zadd(recent_chats_key(msg.sender_id), {msg.receiver_id: timestamp})
        redis_conn.zadd(recent_chats_key(msg.receiver_id), {msg.sender_id: timestamp})
        redis_conn.hincrby(unread_key(msg.receiver_id), msg.sender_id, 1)

        # 4. Trigger real-time notification via async task
        notification_payload = {
            "id": msg.id,
            "sender": msg.sender.username,
            "receiver": msg.receiver.username,
            "timestamp": msg.timestamp.isoformat(),
        }
        send_realtime_notification.delay(msg.receiver_id, notification_payload)

        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)


# --------------------------
# Decrypt a single message
# --------------------------
class DecryptMessageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        methods=['POST'],
        request=MessageDecryptSerializer,
        responses={
            200: {'decrypted_message': 'str'},
            400: {'error': 'Invalid request data'},
            403: {'error': 'Forbidden'},
            500: {'error': 'Internal server error'}
        },
        description='Decrypt a message.',
        summary='Decrypt message'
    )
    def post(self, request, *args, **kwargs):
        serializer = MessageDecryptSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        message_id = serializer.validated_data['message_id']

        try:
            message_obj = get_object_or_404(Message, id=message_id)

            if request.user not in [message_obj.sender, message_obj.receiver]:
                return Response(
                    {"error": "You are not authorized to decrypt this message."},
                    status=status.HTTP_403_FORBIDDEN
                )

            fernet = Fernet(settings.FERNET_KEY)
            decrypted_text = fernet.decrypt(bytes(message_obj.ciphertext)).decode('utf-8')

            return Response({'decrypted_message': decrypted_text}, status=status.HTTP_200_OK)

        except InvalidToken:
            return Response({'error': 'Invalid or corrupt data.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --------------------------
# Chat history (decrypt all)
# --------------------------
@extend_schema(
    summary="Retrieve and Decrypt Chat History",
    description="Fetches the full message history between the authenticated user and the specified user. It decrypts all messages and returns them.",
    parameters=[
        OpenApiParameter(
            name='username',
            type=str,
            location=OpenApiParameter.PATH,
            required=True,
            description='The username of the other participant in the chat.'
        )
    ],
    responses={
        200: OpenApiTypes.OBJECT,
        401: {"description": "Authentication required"},
        404: {"description": "User not found"}
    },
    examples=[
        OpenApiExample(
            "Successful Response Example",
            value={
                "id": 101,
                "sender": "alice",
                "receiver": "bob",
                "timestamp": "2025-09-01T12:34:56Z",
                "message": "Hello there!"
            }
        )
    ]
)


# class ChatHistoryView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, username, *args, **kwargs):
#         other_user = get_object_or_404(User, username=username)
#         redis_conn = r()
#         key = chat_key(request.user.id, other_user.id)
#         fernet = Fernet(settings.FERNET_KEY)
#         response_data = []

#         # When fetching history, mark messages from the other user as read.
#         redis_conn.hdel(unread_key(request.user.id), other_user.id)

#         # 1. Try to fetch from Redis cache first
#         cached_messages_json = redis_conn.lrange(key, 0, 99)
        
#         if cached_messages_json:
#             # CORRECT: Parse all JSON strings into a list of dictionaries ONCE.
#             cached_messages = [json.loads(msg) for msg in cached_messages_json]
#             sender_ids = {
#                 msg.get('sender_id') for msg in cached_messages if msg.get('sender_id') is not None
#             }

#             users = User.objects.filter(id__in=sender_ids)
#             user_map = {user.id: user.username for user in users}

#             # CORRECT: Loop directly over the list of dictionaries.
#             for msg in cached_messages: # `msg` is now a dictionary.
#                 # REMOVED: The redundant line `msg = json.loads(msg_json)` is gone.
#                 sender_id = msg.get('sender_id')
#                 if not sender_id:
#                     continue # Skip this malformed message
#                 try:
#                     # Note: The `bytes()` constructor here is not needed since you are encoding a string.
#                     # decrypted_message = fernet.decrypt(msg['ciphertext'].encode('latin1')).decode('utf-8')
#                     encrypted_bytes = base64.b64decode(msg['ciphertext'])
#                     decrypted_message = fernet.decrypt(encrypted_bytes).decode('utf-8')
#                 except (InvalidToken, base64.binascii.Error):
#                     decrypted_message = "[Decryption Failed]"
                
#                 sender_username = user_map.get(msg['sender_id'], "Unknown User")
                
#                 response_data.append({
#                     'id': msg['id'],
#                     'sender': sender_username,
#                     'receiver': other_user.username if sender_username == request.user.username else request.user.username,
#                     'timestamp': msg['timestamp'],
#                     'message': decrypted_message
#                 })
            
#             response_data.reverse()
#             return Response(response_data)

#         # 2. Cache miss: Fallback to database (This section was already correct)
#         messages = Message.objects.filter(
#             (Q(sender=request.user, receiver=other_user)) |
#             (Q(sender=other_user, receiver=request.user))
#         ).order_by('timestamp')

#         cache_pipeline = redis_conn.pipeline()
#         for msg in messages:
#             try:
#                 decrypted_message = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
#             except InvalidToken:
#                 decrypted_message = "[Decryption Failed]"
            
#             response_data.append({
#                 'id': msg.id,
#                 'sender': msg.sender.username,
#                 'receiver': msg.receiver.username,
#                 'timestamp': msg.timestamp,
#                 'message': decrypted_message
#             })
            
#             message_payload = {
#                 "id": msg.id,
#                 "sender_id": msg.sender.id,
#                 "ciphertext": base64.b64encode(bytes(msg.ciphertext)).decode('utf-8'),
#                 "timestamp": msg.timestamp.isoformat(),
#             }
#             cache_pipeline.lpush(key, json.dumps(message_payload))
        
#         if messages:
#             cache_pipeline.ltrim(key, 0, 99)
#             cache_pipeline.execute()

#         return Response(response_data)





class ChatHistoryView(APIView):
    """
    API view to retrieve chat history between two users.
    Supports caching for the 100 most recent messages and
    cursor-based pagination to load older messages.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, username, *args, **kwargs):
        # Check for the pagination cursor in the query parameters
        before_timestamp_str = request.query_params.get('before_timestamp', None)
        before_timestamp = None
        if before_timestamp_str:
            before_timestamp = parse_datetime(before_timestamp_str)

        other_user = get_object_or_404(User, username=username)
        redis_conn = r()
        key = chat_key(request.user.id, other_user.id)
        fernet = Fernet(settings.FERNET_KEY)
        response_data = []

        # --- Path A: Initial Load (No Cursor) ---
        if not before_timestamp:
            # When fetching the latest history, mark messages from this user as read.
            redis_conn.hdel(unread_key(request.user.id), other_user.id)

            # 1. Try to fetch the latest 100 messages from Redis cache
            cached_messages_json = redis_conn.lrange(key, 0, 99)
            
            if cached_messages_json:
                # CACHE HIT: Build the response from cached data
                cached_messages = [json.loads(msg) for msg in cached_messages_json]
                sender_ids = { msg.get('sender_id') for msg in cached_messages if msg.get('sender_id') is not None }
                
                users = User.objects.filter(id__in=sender_ids)
                user_map = {user.id: user.username for user in users}

                for msg in cached_messages:
                    sender_id = msg.get('sender_id')
                    if not sender_id: continue
                    try:
                        encrypted_bytes = base64.b64decode(msg['ciphertext'])
                        decrypted_message = fernet.decrypt(encrypted_bytes).decode('utf-8')
                    except (InvalidToken, base64.binascii.Error):
                        decrypted_message = "[Decryption Failed]"
                    
                    sender_username = user_map.get(msg['sender_id'], "Unknown User")
                    
                    response_data.append({
                        'id': msg.get('id'),
                        'sender': sender_username,
                        'receiver': other_user.username if sender_username == request.user.username else request.user.username,
                        'timestamp': msg.get('timestamp'),
                        'message': decrypted_message
                    })
                
                response_data.reverse() # Reverse to show oldest first, newest last
                return Response(response_data)

            # 2. CACHE MISS: Fallback to the database for the initial load
            messages = Message.objects.filter(
                (Q(sender=request.user, receiver=other_user)) |
                (Q(sender=other_user, receiver=request.user))
            ).order_by('-timestamp')[:100] # Get the 100 most recent messages

            cache_pipeline = redis_conn.pipeline()
            # Delete the key to ensure a clean repopulation
            cache_pipeline.delete(key) 

            for msg in messages:
                # The response data is built in reverse chronological order
                try:
                    decrypted_message = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
                except InvalidToken:
                    decrypted_message = "[Decryption Failed]"
                
                response_data.append({
                    'id': msg.id,
                    'sender': msg.sender.username,
                    'receiver': msg.receiver.username,
                    'timestamp': msg.timestamp.isoformat(),
                    'message': decrypted_message
                })
                
                # The cache is populated in reverse chronological order (newest first)
                message_payload = {
                    "id": msg.id,
                    "sender_id": msg.sender.id,
                    "ciphertext": base64.b64encode(bytes(msg.ciphertext)).decode('utf-8'),
                    "timestamp": msg.timestamp.isoformat(),
                }
                cache_pipeline.lpush(key, json.dumps(message_payload))
            
            if messages:
                cache_pipeline.ltrim(key, 0, 99)
                cache_pipeline.execute()
            
            response_data.reverse() # Reverse to show oldest first, newest last
            return Response(response_data)

        # --- Path B: Paginating for Older Messages (Cursor is Present) ---
        else:
            # We are fetching older messages, so we go STRAIGHT to the database.
            # No need to check or update the Redis cache for these historical queries.
            messages = Message.objects.filter(
                (Q(sender=request.user, receiver=other_user)) |
                (Q(sender=other_user, receiver=request.user)),
                timestamp__lt=before_timestamp  # <-- The key pagination filter
            ).order_by('-timestamp')[:50]  # <-- Get the next 50 messages in a "page"

            for msg in messages:
                try:
                    decrypted_message = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
                except InvalidToken:
                    decrypted_message = "[Decryption Failed]"
                
                response_data.append({
                    'id': msg.id,
                    'sender': msg.sender.username,
                    'receiver': msg.receiver.username,
                    'timestamp': msg.timestamp.isoformat(),
                    'message': decrypted_message
                })

            response_data.reverse() # Reverse to show oldest first, newest last for this page
            return Response(response_data)




# --------------------------
# Recent Chats
# --------------------------
# class RecentChatsAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         key = recent_chats_key(request.user.id)
#         cached = cache.get(key)
#         if cached:
#             return Response(cached)

#         user = request.user

#         messages = Message.objects.annotate(
#             chat_id_1=models.functions.Least('sender_id', 'receiver_id'),
#             chat_id_2=models.functions.Greatest('sender_id', 'receiver_id')
#         ).filter(Q(sender=user) | Q(receiver=user)) \
#          .order_by('chat_id_1', 'chat_id_2', '-timestamp') \
#          .distinct('chat_id_1', 'chat_id_2')

#         data = RecentChatSerializer(messages, many=True, context={'request': request}).data
#         cache.set(key, data, timeout=settings.CACHE_TTL_MED)
#         return Response(data)


#TODO: To make this api fast, we can remove the step of decryption and just send the name of the user who sent the message withoout last message
# class RecentChatsAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         user_id = request.user.id
#         redis_conn = r()

#         # 1. Get ordered list of other user IDs from the Sorted Set
#         other_user_ids = [int(uid) for uid in redis_conn.zrevrange(recent_chats_key(user_id), 0, -1)]
#         if not other_user_ids:
#             return Response([])

#         # 2. ADDED BACK: Get all unread counts in one go from the Redis Hash
#         unread_counts = {int(k): int(v) for k, v in redis_conn.hgetall(unread_key(user_id)).items()}
        
#         # 3. Get user details from DB in a single query
#         users = User.objects.filter(id__in=other_user_ids)
#         user_map = {user.id: user for user in users}
        
#         # 4. Get the last message for each chat using a pipeline for efficiency
#         pipe = redis_conn.pipeline()
#         for other_id in other_user_ids:
#             pipe.lindex(chat_key(user_id, other_id), 0)
#         last_messages_json = pipe.execute()
        
#         # 5. Assemble the final response, now including unread_count
#         response_data = []
#         fernet = Fernet(settings.FERNET_KEY)

#         for i, other_id in enumerate(other_user_ids):
#             user_obj = user_map.get(other_id)
#             if not user_obj:
#                 continue
                
#             last_msg_str = last_messages_json[i]
#             last_message_text = "No messages yet"
#             last_message_time = None
#             chat_id = other_id 

#             if last_msg_str:
#                 last_msg = json.loads(last_msg_str)
#                 chat_id = last_msg.get('id', other_id)
#                 try:
#                     last_message_text = fernet.decrypt(last_msg['ciphertext'].encode('latin1')).decode('utf-8')
#                 except InvalidToken:
#                     last_message_text = "[Encrypted Message]"
#                 last_message_time = last_msg['timestamp']

#             response_data.append({
#                 "id": chat_id,
#                 "other_user": {
#                     "id": user_obj.id,
#                     "username": user_obj.username,
#                     "full_name": user_obj.full_name
#                 },
#                 "last_message_preview": last_message_text,
#                 "timestamp": last_message_time,
#                 # ADDED BACK: Get the count for this user, defaulting to 0
#                 "unread_count": unread_counts.get(other_id, 0)
#             })
            
#         return Response(response_data)


# Make sure all these imports are at the top of your views.py
import base64
# class RecentChatsAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         user_id = request.user.id
#         redis_conn = r()
#         response_data = []
#         fernet = Fernet(settings.FERNET_KEY)

#         # 1. Try to fetch the list of recent chat partners from Redis first
#         other_user_ids = [int(uid) for uid in redis_conn.zrevrange(recent_chats_key(user_id), 0, -1)]

#         # --- CACHE HIT PATH ---
#         # If Redis returned a list of users, use the fast, fully-cached method
#         if other_user_ids:
#             unread_counts = {int(k): int(v) for k, v in redis_conn.hgetall(unread_key(user_id)).items()}
#             users = User.objects.filter(id__in=other_user_ids)
#             user_map = {user.id: user for user in users}
            
#             pipe = redis_conn.pipeline()
#             for other_id in other_user_ids:
#                 pipe.lindex(chat_key(user_id, other_id), 0)
#             last_messages_json = pipe.execute()
            
#             for i, other_id in enumerate(other_user_ids):
#                 user_obj = user_map.get(other_id)
#                 if not user_obj: continue
                
#                 last_msg_str = last_messages_json[i]
#                 last_message_preview = "No messages yet"
#                 last_message_time = None
#                 chat_id = other_id

#                 if last_msg_str:
#                     last_msg = json.loads(last_msg_str)
#                     chat_id = last_msg.get('id', other_id)
#                     last_message_time = last_msg.get('timestamp')
#                     try:
#                             ciphertext_b64 = last_msg['ciphertext']
#                             ciphertext_bytes = base64.b64decode(ciphertext_b64)  # 🔑 Decode it back
#                             decrypted_text = fernet.decrypt(ciphertext_bytes).decode('utf-8')

#                             if last_msg.get('sender_id') == user_id:
#                                 last_message_preview = f"You: {decrypted_text}"
#                             else:
#                                 last_message_preview = decrypted_text
#                     except InvalidToken:
#                             last_message_preview = "[Decryption Failed]"
                
#                 response_data.append({
#                     "id": chat_id, "other_user": {"id": user_obj.id, "username": user_obj.username, "full_name": user_obj.full_name},
#                     "last_message_preview": last_message_preview, "timestamp": last_message_time,
#                     "unread_count": unread_counts.get(other_id, 0)
#                 })
#             return Response(response_data)

#         # --- CACHE MISS / DATABASE FALLBACK PATH ---
#         # If Redis was empty, query the database to find the recent chats
        
#         latest_messages = Message.objects.filter(
#             Q(sender_id=user_id) | Q(receiver_id=user_id)
#         ).annotate(
#             chat_partner_id=Case(
#                 When(sender_id=user_id, then=DjF('receiver_id')),
#                 default=DjF('sender_id'),
#                 output_field=IntegerField()
#             )
#         ).order_by('chat_partner_id', '-timestamp').distinct('chat_partner_id')


#         if not latest_messages:
#             return Response([])

#         unread_counts = {int(k): int(v) for k, v in redis_conn.hgetall(unread_key(user_id)).items()}
#         cache_pipe = redis_conn.pipeline()
        
#         for msg in latest_messages:
#             other_user = msg.sender if msg.receiver_id == user_id else msg.receiver
            
#             try:
#                 decrypted_preview = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
#                 if msg.sender_id == user_id:
#                     decrypted_preview = f"You: {decrypted_preview}"
#             except InvalidToken:
#                 decrypted_preview = "[Decryption Failed]"
            
#             response_data.append({
#                 "id": msg.id,
#                 "other_user": {"id": other_user.id, "username": other_user.username, "full_name": other_user.full_name},
#                 "last_message_preview": decrypted_preview,
#                 "timestamp": msg.timestamp.isoformat(),
#                 "unread_count": unread_counts.get(other_user.id, 0)
#             })

#             # Populate the cache for the next request
#             timestamp = int(msg.timestamp.timestamp())
#             cache_pipe.zadd(recent_chats_key(user_id), {other_user.id: timestamp})
        
#         cache_pipe.execute()
#         return Response(response_data)



# class RecentChatsAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         user_id = request.user.id
#         redis_conn = r()
#         response_data = []
#         fernet = Fernet(settings.FERNET_KEY)

#         # 1. Fetch the list of recent chat partners from Redis
#         other_user_ids = [int(uid) for uid in redis_conn.zrevrange(recent_chats_key(user_id), 0, -1)]

#         # --- CACHE HIT PATH ---
#         if other_user_ids:
#             # This path is mostly correct, we just need to fix the 'id' fallback
#             unread_counts = {int(k): int(v) for k, v in redis_conn.hgetall(unread_key(user_id)).items()}
#             users = User.objects.filter(id__in=other_user_ids)
#             user_map = {user.id: user for user in users}
            
#             pipe = redis_conn.pipeline()
#             for other_id in other_user_ids:
#                 pipe.lindex(chat_key(user_id, other_id), 0)
#             last_messages_json = pipe.execute()
            
#             for i, other_id in enumerate(other_user_ids):
#                 user_obj = user_map.get(other_id)
#                 if not user_obj: continue
                
#                 last_msg_str = last_messages_json[i]
#                 last_message_preview = "No messages yet"
#                 last_message_time = None
#                 message_id = None # Default to None

#                 if last_msg_str:
#                     last_msg = json.loads(last_msg_str)
#                     message_id = last_msg.get('id') # <-- FIX: Don't fall back to other_id
#                     last_message_time = last_msg.get('timestamp')
#                     try:
#                         ciphertext_b64 = last_msg['ciphertext']
#                         ciphertext_bytes = base64.b64decode(ciphertext_b64)
#                         decrypted_text = fernet.decrypt(ciphertext_bytes).decode('utf-8')

#                         if last_msg.get('sender_id') == user_id:
#                             last_message_preview = f"You: {decrypted_text}"
#                         else:
#                             last_message_preview = decrypted_text
#                     except (InvalidToken, base64.binascii.Error):
#                         last_message_preview = "[Decryption Failed]"
                
#                 response_data.append({
#                     "id": message_id, "other_user": {"id": user_obj.id, "username": user_obj.username, "full_name": user_obj.full_name},
#                     "last_message_preview": last_message_preview, "timestamp": last_message_time,
#                     "unread_count": unread_counts.get(other_id, 0)
#                 })
#             return Response(response_data)

#         # --- CACHE MISS / DATABASE FALLBACK PATH ---
#         latest_messages = Message.objects.filter(
#             Q(sender_id=user_id) | Q(receiver_id=user_id)
#         ).annotate(
#             chat_partner_id=Case(
#                 When(sender_id=user_id, then=DjF('receiver_id')),
#                 default=DjF('sender_id'),
#                 output_field=IntegerField()
#             )
#         ).order_by('chat_partner_id', '-timestamp').distinct('chat_partner_id')

#         if not latest_messages:
#             return Response([])

#         unread_counts = {int(k): int(v) for k, v in redis_conn.hgetall(unread_key(user_id)).items()}
#         cache_pipe = redis_conn.pipeline()
        
#         # Sort messages by timestamp descending to build the final response
#         sorted_messages = sorted(latest_messages, key=lambda m: m.timestamp, reverse=True)

#         for msg in sorted_messages:
#             other_user = msg.sender if msg.receiver_id == user_id else msg.receiver
            
#             try:
#                 decrypted_preview = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
#                 if msg.sender_id == user_id:
#                     decrypted_preview = f"You: {decrypted_preview}"
#             except InvalidToken:
#                 decrypted_preview = "[Decryption Failed]"
            
#             response_data.append({
#                 "id": msg.id,
#                 "other_user": {"id": other_user.id, "username": other_user.username, "full_name": other_user.full_name},
#                 "last_message_preview": decrypted_preview,
#                 "timestamp": msg.timestamp.isoformat(),
#                 "unread_count": unread_counts.get(other_user.id, 0)
#             })

#             # --- FIX: FULLY REPOPULATE THE CACHE ---
#             # 1. Re-populate the sorted set of recent chats
#             timestamp = int(msg.timestamp.timestamp())
#             cache_pipe.zadd(recent_chats_key(user_id), {other_user.id: timestamp})
            
#             # 2. Re-populate the last message for this specific chat history
#             message_payload = {
#                 "id": msg.id,
#                 "sender_id": msg.sender_id,
#                 "ciphertext": base64.b64encode(bytes(msg.ciphertext)).decode('utf-8'),
#                 "timestamp": msg.timestamp.isoformat(),
#             }
#             chat_hist_key = chat_key(user_id, other_user.id)
#             # Delete the old list and push the latest message to ensure it's clean
#             cache_pipe.delete(chat_hist_key) 
#             cache_pipe.lpush(chat_hist_key, json.dumps(message_payload))
        
#         cache_pipe.execute()
#         return Response(response_data)




# from django.conf import settings
# from django.db.models import Q, Case, When, IntegerField
# from django.db.models import F as DjF
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from redis import Redis as r
# from cryptography.fernet import Fernet, InvalidToken
# import json
# import base64

# # Assuming you have these models and keys defined
# from .models import CustomUser as User, Message
# from .redis_keys import recent_chats_key, unread_key, chat_key


class RecentChatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        redis_conn = r()
        response_data = []
        fernet = Fernet(settings.FERNET_KEY)

        # 1. Fetch the list of recent chat partners from Redis
        other_user_ids = [int(uid) for uid in redis_conn.zrevrange(recent_chats_key(user_id), 0, -1)]

        # --- CACHE HIT PATH ---
        if other_user_ids:
            unread_counts = {int(k): int(v) for k, v in redis_conn.hgetall(unread_key(user_id)).items()}
            
            # ✅ CHANGE 1: Use select_related to efficiently fetch the user's profile
            users = User.objects.select_related('profile').filter(id__in=other_user_ids)
            user_map = {user.id: user for user in users}
            
            pipe = redis_conn.pipeline()
            for other_id in other_user_ids:
                pipe.lindex(chat_key(user_id, other_id), 0)
            last_messages_json = pipe.execute()
            
            for i, other_id in enumerate(other_user_ids):
                user_obj = user_map.get(other_id)
                if not user_obj: continue
                
                last_msg_str = last_messages_json[i]
                last_message_preview = "No messages yet"
                last_message_time = None
                message_id = None

                if last_msg_str:
                    last_msg = json.loads(last_msg_str)
                    message_id = last_msg.get('id')
                    last_message_time = last_msg.get('timestamp')
                    try:
                        ciphertext_b64 = last_msg['ciphertext']
                        ciphertext_bytes = base64.b64decode(ciphertext_b64)
                        decrypted_text = fernet.decrypt(ciphertext_bytes).decode('utf-8')

                        if last_msg.get('sender_id') == user_id:
                            last_message_preview = f"You: {decrypted_text}"
                        else:
                            last_message_preview = decrypted_text
                    except (InvalidToken, base64.binascii.Error):
                        last_message_preview = "[Decryption Failed]"
                
                # ✅ CHANGE 2: Safely get avatar_url from the user's profile
                avatar_url = user_obj.profile.avatar_url if hasattr(user_obj, 'profile') else None
                
                response_data.append({
                    "id": message_id,
                    "other_user": {
                        "id": user_obj.id,
                        "username": user_obj.username,
                        "full_name": user_obj.full_name,
                        "avatar_url": avatar_url # <-- AVATAR URL ADDED
                    },
                    "last_message_preview": last_message_preview, "timestamp": last_message_time,
                    "unread_count": unread_counts.get(other_id, 0)
                })
            return Response(response_data)

        # --- CACHE MISS / DATABASE FALLBACK PATH ---
        # ✅ CHANGE 3: Fetch related sender/receiver profiles in the initial query
        latest_messages = Message.objects.select_related(
            'sender__profile', 'receiver__profile'
        ).filter(
            Q(sender_id=user_id) | Q(receiver_id=user_id)
        ).annotate(
            chat_partner_id=Case(
                When(sender_id=user_id, then=DjF('receiver_id')),
                default=DjF('sender_id'),
                output_field=IntegerField()
            )
        ).order_by('chat_partner_id', '-timestamp').distinct('chat_partner_id')

        if not latest_messages:
            return Response([])

        unread_counts = {int(k): int(v) for k, v in redis_conn.hgetall(unread_key(user_id)).items()}
        cache_pipe = redis_conn.pipeline()
        
        sorted_messages = sorted(latest_messages, key=lambda m: m.timestamp, reverse=True)

        for msg in sorted_messages:
            other_user = msg.sender if msg.receiver_id == user_id else msg.receiver
            
            try:
                decrypted_preview = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
                if msg.sender_id == user_id:
                    decrypted_preview = f"You: {decrypted_preview}"
            except InvalidToken:
                decrypted_preview = "[Decryption Failed]"

            # ✅ CHANGE 4: Safely get the avatar_url here as well
            avatar_url = other_user.profile.avatar_url if hasattr(other_user, 'profile') else None
            
            response_data.append({
                "id": msg.id,
                "other_user": {
                    "id": other_user.id,
                    "username": other_user.username,
                    "full_name": other_user.full_name,
                    "avatar_url": avatar_url # <-- AVATAR URL ADDED
                },
                "last_message_preview": decrypted_preview,
                "timestamp": msg.timestamp.isoformat(),
                "unread_count": unread_counts.get(other_user.id, 0)
            })

            # Re-populate the cache
            timestamp = int(msg.timestamp.timestamp())
            cache_pipe.zadd(recent_chats_key(user_id), {other_user.id: timestamp})
            
            message_payload = {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "ciphertext": base64.b64encode(bytes(msg.ciphertext)).decode('utf-8'),
                "timestamp": msg.timestamp.isoformat(),
            }
            chat_hist_key = chat_key(user_id, other_user.id)
            cache_pipe.delete(chat_hist_key) 
            cache_pipe.lpush(chat_hist_key, json.dumps(message_payload))
        
        cache_pipe.execute()
        return Response(response_data)










# --------------------------
# Unread Counts
# --------------------------
from rest_framework.decorators import api_view, permission_classes

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_counts(request):
    counts = r().hgetall(unread_key(request.user.id))  # {b'2': b'3', ...}
    result = {int(k.decode()): int(v.decode()) for k, v in counts.items()}
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_read(request):
    other_id = int(request.data.get("other_user_id"))
    r().hdel(unread_key(request.user.id), str(other_id))
    return Response({"ok": True})



from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample

CHAT_PAGE_SIZE = 50

class OldChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Chat History",
        description="...",
        tags=["Chat"],
        parameters=[
            OpenApiParameter(
                name="username",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                required=True,
            ),
            # ✅ REMOVE 'example' from here
            OpenApiParameter(
                name="before_timestamp",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                required=False,
                description="The ISO 8601 timestamp of the oldest message you have.",
            ),
        ],
        # ✅ ADD the 'examples' block here instead
        examples=[
            OpenApiExample(
                'Example 1: First page of history',
                summary='No cursor provided',
                description='When no timestamp is provided, you get the most recent page of historical messages.',
                value={} # No query params
            ),
            OpenApiExample(
                'Example 2: Paginate older messages',
                summary='Using a timestamp cursor',
                description='Provide the timestamp of the oldest message you have to get the next page.',
                value={'before_timestamp': '2025-09-15T10:30:00Z'}
            )
        ],
        responses={
            200: MessageSerializer(many=True),
            404: {"description": "User not found."}
        }
    )
    

    # @extend_schema(...) # Your existing schema decorator
    def get(self, request, username, *args, **kwargs):
        user1 = request.user
        user2 = get_object_or_404(User, username=username)
        cursor_timestamp_str = request.query_params.get('before_timestamp')

        # 1. Fetch encrypted messages from the database
        queryset = Message.objects.select_related('sender', 'receiver').filter(
            (Q(sender=user1) & Q(receiver=user2)) |
            (Q(sender=user2) & Q(receiver=user1))
        ).order_by('-timestamp')

        if cursor_timestamp_str:
            cursor_timestamp = parse_datetime(cursor_timestamp_str)
            if cursor_timestamp:
                queryset = queryset.filter(timestamp__lt=cursor_timestamp)

        messages = queryset[:CHAT_PAGE_SIZE]

        # 2. Manually decrypt and build the response list, just like in RecentChatsAPIView
        fernet = Fernet(settings.FERNET_KEY)
        response_data = []
        
        for msg in messages:
            try:
                decrypted_text = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
            except InvalidToken:
                decrypted_text = "[Message could not be decrypted]"
            
            response_data.append({
                'id': msg.id,
                'sender': msg.sender.username,
                'receiver': msg.receiver.username,
                'message': decrypted_text,  # The decrypted plain text
                'timestamp': msg.timestamp.isoformat(),
                # 'is_edited': msg.is_edited,
            })

        # 3. Return the manually constructed list of decrypted messages
        return Response(response_data)




# your_app/views.py
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from rest_framework.permissions import IsAuthenticated
# from django.db.models import Q
import redis
# import json
# import base64

# from .models import Message
from . import redis_helpers

class DeleteMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, message_id, *args, **kwargs):
        user = request.user
        
        try:
            message = Message.objects.get(id=message_id, sender=user)
        except Message.DoesNotExist:
            return Response(
                {"error": "Message not found or you don't have permission to delete it."},
                status=status.HTTP_404_NOT_FOUND
            )

        other_user_id = message.receiver_id if message.sender_id == user.id else message.sender_id
        
        # Reconstruct the cache payload for LREM
        message_payload = {
            "id": message.id,
            "sender_id": message.sender_id,
            "ciphertext": base64.b64encode(bytes(message.ciphertext)).decode('utf-8'),
            "timestamp": message.timestamp.isoformat(),
        }
        json_string_to_remove = json.dumps(message_payload)

        # Delete the message from the primary database
        message.delete()
        
        try:
            redis_conn = redis.from_url(settings.REDIS_URL, decode_responses=True)
            chat_history_key = redis_helpers.chat_key(user.id, other_user_id)
            
            # 1. Remove the specific message from the chat history list
            redis_conn.lrem(chat_history_key, 0, json_string_to_remove)

            # 2. ✅ UPDATE THE RECENT CHATS CACHE
            # Find the new latest message in the conversation from the database
            new_latest_message = Message.objects.filter(
                (Q(sender=user) & Q(receiver_id=other_user_id)) |
                (Q(sender_id=other_user_id) & Q(receiver=user))
            ).order_by('-timestamp').first()

            # Get the cache keys for both users' recent chats
            user_recent_key = redis_helpers.recent_chats_key(user.id)
            other_user_recent_key = redis_helpers.recent_chats_key(other_user_id)

            if new_latest_message:
                # If messages still exist, update the sorted set with the new latest timestamp
                new_timestamp = int(new_latest_message.timestamp.timestamp())
                redis_conn.zadd(user_recent_key, {str(other_user_id): new_timestamp})
                redis_conn.zadd(other_user_recent_key, {str(user.id): new_timestamp})
            else:
                # If no messages are left, remove the conversation from each user's recent chats
                redis_conn.zrem(user_recent_key, str(other_user_id))
                redis_conn.zrem(other_user_recent_key, str(user.id))

        except Exception as e:
            print(f"Could not update cache for deleted message {message_id}: {e}")

        return Response(status=status.HTTP_204_NO_CONTENT)

