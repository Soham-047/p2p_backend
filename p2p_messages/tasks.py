from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Message
from .serializers import MessageSerializer
from users.models import CustomUser

@shared_task
def notify_receiver_new_message(message_id):
    """
    Send real-time + email notification asynchronously when a new message is created.
    """
    try:
        msg = Message.objects.select_related("sender", "receiver").get(id=message_id)

        # --- WebSocket notify ---
        channel_layer = get_channel_layer()
        payload = {
            "id": msg.id,
            "sender": msg.sender.username,
            "receiver": msg.receiver.username,
            "timestamp": msg.timestamp.isoformat(),
        }
        async_to_sync(channel_layer.group_send)(
            f"user_{msg.receiver_id}",
            {"type": "chat_message", "payload": {"event": "NEW_MESSAGE", "data": payload}},
        )

        # --- Email notify ---
        send_mail(
            subject=f"New message from {msg.sender.username}",
            message=f"You have received a new message at {msg.timestamp}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[msg.receiver.email],
            fail_silently=True,
        )

    except Message.DoesNotExist:
        pass

@shared_task
def clean_old_unread_counters():
    """
    Periodic task to clean stale unread counters.
    """
    from .redis_helpers import r
    for key in r().scan_iter("unread:*"):
        r().expire(key, 60 * 60 * 24)  # 24h TTL refresh

# chatapp/tasks.py
from celery import shared_task
from django.core.cache import cache
from .redis_helpers import r, recent_chats_key, unread_key
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@shared_task
def invalidate_recent_chats_cache(user_id, receiver_id):
    cache.delete_many([
        recent_chats_key(user_id),
        recent_chats_key(receiver_id),
    ])


@shared_task
def increment_unread_counter(receiver_id, sender_id):
    r().hincrby(unread_key(receiver_id), str(sender_id), 1)


@shared_task
def send_realtime_notification(receiver_id, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{receiver_id}",
        {"type": "chat_message", "payload": {"event": "NEW_MESSAGE", "data": payload}},
    )

