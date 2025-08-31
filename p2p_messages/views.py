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
class MessageListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Fetch messages where user is sender or receiver
        messages = Message.objects.filter(Q(sender=user) | Q(receiver=user)).order_by('-timestamp')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MessageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(sender=request.user)  # Automatically set sender
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
    """
    Provides a list of recent chats for the authenticated user.
    Each chat is represented by its most recent message.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        user = request.user

        # 1. Annotate messages with a consistent ID for each conversation pair.
        #    Least/Greatest ensures that a chat between user 1 and 2 is the
        #    same as a chat between user 2 and 1.
        messages = Message.objects.annotate(
            chat_id_1=Least('sender_id', 'receiver_id'),
            chat_id_2=Greatest('sender_id', 'receiver_id')
        )

        # 2. Filter these messages to only include those involving the current user.
        messages = messages.filter(Q(sender=user) | Q(receiver=user))

        # 3. Order by the consistent chat ID and then by timestamp descending.
        #    Then, get the distinct (first) message for each chat, which will
        #    be the latest one because of the ordering.
        recent_messages = messages.order_by(
            'chat_id_1', 
            'chat_id_2', 
            '-timestamp'
        ).distinct(
            'chat_id_1', 
            'chat_id_2'
        )

        # A more readable, but potentially less performant approach for non-PostgreSQL DBs
        # is to loop, but this is generally discouraged due to the N+1 query problem.
        # The query above is preferred.

        # Serialize the final list of messages
        serializer = RecentChatSerializer(
            recent_messages, 
            many=True, 
            context={'request': request}
        )
        return Response(serializer.data)