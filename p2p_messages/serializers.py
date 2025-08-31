from rest_framework import serializers
from .models import Message
from users.models import CustomUser as User
from django.conf import settings
from cryptography.fernet import Fernet,InvalidToken


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.ReadOnlyField(source='sender.username')
    # reciever = serializers.ReadOnlyField(source='receiver.username')  # Read-only sender username

    class Meta:
        model = Message
        fields = ['id', 'sender', 'receiver', 'ciphertext', 'timestamp']



class MessageDecryptSerializer(serializers.Serializer):
    """
    Serializer to validate the incoming message ID.
    """
    message_id = serializers.IntegerField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username','full_name']

class RecentChatSerializer(serializers.ModelSerializer):
    """
    Serializes a Message object into a chat list format.
    """
    # We will represent the other user in the chat with a nested serializer
    other_user = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'other_user', 'last_message_preview', 'timestamp']
        ordering = ['-timestamp']

    def get_other_user(self,obj):
        """
        Returns the user who is not the currently authenticated user.
        """

        if obj.sender == self.context['request'].user:
            return UserSerializer(obj.receiver).data
        else:
            return UserSerializer(obj.sender).data
        
    def get_last_message_preview(self, obj):
        """
        Decrypts the ciphertext to show a message preview.
        """
        try:
            fernet = Fernet(settings.FERNET_KEY) 
            decrypted_text = fernet.decrypt(bytes(obj.ciphertext)).decode('utf-8')
            return decrypted_text[:50] + '...' if len(decrypted_text) > 50 else decrypted_text
        except InvalidToken:
            return "[Decryption Failed]"