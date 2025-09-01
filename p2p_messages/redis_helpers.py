# chatapp/redis_helpers.py
from django_redis import get_redis_connection

def r():
    return get_redis_connection("default")

def chat_key(user_id_a, user_id_b):
    a, b = sorted([user_id_a, user_id_b])
    return f"chat:{a}:{b}"

def recent_chats_key(user_id):
    return f"recent_chats:{user_id}"

def unread_key(user_id):
    return f"unread:{user_id}"  # hash: {other_user_id: count}
