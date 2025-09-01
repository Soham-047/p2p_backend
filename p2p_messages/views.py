# chatapp/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Message
from .serializers import MessageSerializer, MessageDecryptSerializer, UserSerializer, RecentChatSerializer
from django.db.models import Q,Subquery, OuterRef
import json
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views import View
from cryptography.fernet import Fernet, InvalidToken
from .models import Message
from users.models import CustomUser as User
from drf_spectacular.openapi import OpenApiResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.db.models.functions import Least, Greatest
from django.core.cache import cache
from .redis_helpers import r, chat_key, recent_chats_key, unread_key
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


from .tasks import (
    invalidate_recent_chats_cache,
    increment_unread_counter,
    send_realtime_notification,
)

class MessageListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MessageSerializer(data=request.data)
        if serializer.is_valid():
            msg = serializer.save(sender=request.user)

            # Async tasks
            invalidate_recent_chats_cache.delay(request.user.id, msg.receiver_id)
            increment_unread_counter.delay(msg.receiver_id, msg.sender_id)

            payload = {
                "id": msg.id,
                "sender": msg.sender.username,
                "receiver": msg.receiver.username,
                "timestamp": msg.timestamp.isoformat(),
            }
            send_realtime_notification.delay(msg.receiver_id, payload)

            return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Fetch messages where user is sender or receiver
        messages = Message.objects.filter(Q(sender=user) | Q(receiver=user)).order_by('-timestamp')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


class DecryptMessageView(APIView):
    """
    Decrypts a message using DRF and Token Authentication.
    """
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
        # Use the serializer to validate the incoming data
        serializer = MessageDecryptSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        message_id = serializer.validated_data['message_id']
        
        try:
            # 1. Get the message from the database
            message_obj = get_object_or_404(Message, id=message_id)

            # 2. !! CRITICAL SECURITY CHECK !!
            if request.user != message_obj.receiver and request.user != message_obj.sender:
                return Response(
                    {"error": "You are not authorized to decrypt this message."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # 3. If authorized, proceed with decryption
            fernet = Fernet(settings.FERNET_KEY)
            decrypted_text = fernet.decrypt(message_obj.ciphertext).decode('utf-8')
            
            return Response({'decrypted_message': decrypted_text}, status=status.HTTP_200_OK)

        except InvalidToken:
            return Response({'error': 'Invalid or corrupt data.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        




@extend_schema(
    summary="Retrieve and Decrypt Chat History",
    description="Fetches the full message history between the authenticated user and the specified user. It decrypts all messages on the server and returns a dictionary mapping each message ID to its plain text content.",
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
        200: OpenApiTypes.OBJECT, # Describes a dictionary/JSON object response
        401: {"description": "Authentication credentials were not provided."},
        404: {"description": "User with the specified username not found."}
    },
    examples=[
        OpenApiExample(
            "Successful Response Example",
            value={
                "101": "Hello there!",
                "102": "This is a decrypted message.",
                "105": "[Decryption Failed]"
            }
        )
    ]
)

class ChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, username, *args, **kwargs):
        # The other user in the chat
        other_user = get_object_or_404(User, username=username)
        
        # Find all messages between the logged-in user and the other user
        messages = Message.objects.filter(
            (Q(sender=request.user) & Q(receiver=other_user)) |
            (Q(sender=other_user) & Q(receiver=request.user))
        ).order_by('timestamp')
        
        fernet = Fernet(settings.FERNET_KEY)
        # Initialize an empty list for our response data
        response_data = []
        
        for msg in messages:
            # For each message, create a dictionary
            message_data = {
                'id': msg.id,
                'sender': msg.sender.username,
                'receiver': msg.receiver.username,
                'timestamp': msg.timestamp
            }
            # Decrypt the message content
            try:
                decrypted_text = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
                message_data['message'] = decrypted_text
            except InvalidToken:
                message_data['message'] = "[Decryption Failed]"
            
            # Add the complete message dictionary to our list
            response_data.append(message_data)
        
        return Response(response_data)
    



class RecentChatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        key = recent_chats_key(request.user.id)
        cached = cache.get(key)
        if cached:
            return Response(cached)

        user = request.user
        from django.db.models.functions import Least, Greatest
        from django.db.models import Q
        from .serializers import RecentChatSerializer
        from .models import Message

        messages = Message.objects.annotate(
            chat_id_1=Least('sender_id', 'receiver_id'),
            chat_id_2=Greatest('sender_id', 'receiver_id')
        ).filter(Q(sender=user) | Q(receiver=user)) \
         .order_by('chat_id_1', 'chat_id_2', '-timestamp') \
         .distinct('chat_id_1', 'chat_id_2')

        data = RecentChatSerializer(messages, many=True, context={'request': request}).data
        cache.set(key, data, timeout=settings.CACHE_TTL_MED)
        return Response(data)
    

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_counts(request):
    """
    Returns a dict {other_user_id: unread_count}
    """
    counts = r().hgetall(unread_key(request.user.id))  # {b'2': b'3', ...}
    result = {int(k.decode()): int(v.decode()) for k, v in counts.items()}
    return Response(result)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_read(request):
    """
    Body: {"other_user_id": 123}
    Resets unread count for conversation (other_user_id -> 0)
    """
    other_id = int(request.data.get("other_user_id"))
    r().hdel(unread_key(request.user.id), str(other_id))
    return Response({"ok": True})