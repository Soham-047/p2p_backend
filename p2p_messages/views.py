# chatapp/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from cryptography.fernet import Fernet, InvalidToken

from users.models import CustomUser as User
from .models import Message
from .serializers import (
    MessageSerializer,
    MessageDecryptSerializer,
    RecentChatSerializer,
)

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from django.core.cache import cache
from .redis_helpers import r, recent_chats_key, unread_key
from .tasks import (
    invalidate_recent_chats_cache,
    increment_unread_counter,
    send_realtime_notification,
)


# --------------------------
# Create + List Messages
# --------------------------
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

    def get(self, request):
        user = request.user
        messages = Message.objects.filter(Q(sender=user) | Q(receiver=user)).order_by('-timestamp')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


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
            decrypted_text = fernet.decrypt(message_obj.ciphertext).decode('utf-8')

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
class ChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, username, *args, **kwargs):
        other_user = get_object_or_404(User, username=username)

        messages = Message.objects.filter(
            (Q(sender=request.user, receiver=other_user)) |
            (Q(sender=other_user, receiver=request.user))
        ).order_by('timestamp')

        fernet = Fernet(settings.FERNET_KEY)
        response_data = []

        for msg in messages:
            data = {
                'id': msg.id,
                'sender': msg.sender.username,
                'receiver': msg.receiver.username,
                'timestamp': msg.timestamp
            }
            try:
                data['message'] = fernet.decrypt(bytes(msg.ciphertext)).decode('utf-8')
            except InvalidToken:
                data['message'] = "[Decryption Failed]"

            response_data.append(data)

        return Response(response_data)


# --------------------------
# Recent Chats
# --------------------------
class RecentChatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        key = recent_chats_key(request.user.id)
        cached = cache.get(key)
        if cached:
            return Response(cached)

        user = request.user

        messages = Message.objects.annotate(
            chat_id_1=models.functions.Least('sender_id', 'receiver_id'),
            chat_id_2=models.functions.Greatest('sender_id', 'receiver_id')
        ).filter(Q(sender=user) | Q(receiver=user)) \
         .order_by('chat_id_1', 'chat_id_2', '-timestamp') \
         .distinct('chat_id_1', 'chat_id_2')

        data = RecentChatSerializer(messages, many=True, context={'request': request}).data
        cache.set(key, data, timeout=settings.CACHE_TTL_MED)
        return Response(data)


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
