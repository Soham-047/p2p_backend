# users/utils.py
import random
import string
from django.contrib.auth import get_user_model

User = get_user_model()

def rand_str(n=4):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def make_username_from_email(email: str) -> str:
    local = email.split("@")[0]
    base = "".join(ch for ch in local if ch.isalnum()) or "user"
    username = f"{base}.{rand_str(4)}"
    # ensure unique
    i = 1
    candidate = username
    while User.objects.filter(username=candidate).exists():
        candidate = f"{username}{i}"
        i += 1
    return candidate

def make_random_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    return "".join(random.choices(chars, k=length))
