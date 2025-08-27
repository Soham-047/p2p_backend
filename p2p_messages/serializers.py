from rest_framework import serializers
from .models import Message

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