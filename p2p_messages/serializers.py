from rest_framework import serializers
from .models import Message
from users.models import CustomUser as User
from django.conf import settings
from cryptography.fernet import Fernet,InvalidToken
from cryptography.fernet import Fernet
# from .fields import Base64BinaryField 
# In your serializers.py or a new fields.py
import base64

class Base64BinaryField(serializers.Field):
    """
    A custom field to handle binary data as a base64-encoded string.
    """
    def to_representation(self, value):
        # This is for the RESPONSE: Converts bytes (from DB) to a Base64 string (for JSON)
        return base64.b64encode(value).decode('utf-8')

    def to_internal_value(self, data):
        # This is for the REQUEST: Converts a Base64 string (from JSON) to bytes (for DB)
        try:
            return base64.b64decode(data)
        except (TypeError, base64.binascii.Error):
            raise serializers.ValidationError("Invalid base64 string.")
        
# In serializers.py

# The custom field from before

# Initialize Fernet. Your key MUST be stored securely in your settings/environment.
# Ensure you have a key named 'FERNET_KEY' in your settings.py
fernet = Fernet(settings.FERNET_KEY)

class MessageSerializer(serializers.ModelSerializer):
    # This field is for the client to SEND plain text. It won't be in the response.
    message = serializers.CharField(write_only=True)
    
    # This field is for the RESPONSE. We still need the custom field to show the
    # saved ciphertext correctly. It's now read-only.
    ciphertext = Base64BinaryField(read_only=True)
    
    sender = serializers.ReadOnlyField(source='sender.username')
    receiver = serializers.SlugRelatedField(
        slug_field="username", 
        queryset=User.objects.all()
    )
    class Meta:
        model = Message
        # Note: 'message' is included here but will only be used for writing.
        fields = ['id', 'sender', 'receiver', 'message', 'ciphertext', 'timestamp']

    def create(self, validated_data):
        """
        This method is called when we save the serializer.
        We will encrypt the message here before creating the Message object.
        """
        # 1. Get the plain text message from the validated data.
        plain_message = validated_data.pop('message')

        # 2. Encrypt the message.
        encrypted_message = fernet.encrypt(plain_message.encode('utf-8'))
        
        # 3. Add the encrypted message to our data under the 'ciphertext' key.
        validated_data['ciphertext'] = encrypted_message

        # 4. Create the Message instance in the database.
        # The sender is added in the view from request.user
        instance = Message.objects.create(**validated_data)
        return instance



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