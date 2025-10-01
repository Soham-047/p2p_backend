# users/utils.py
import random
import string
from django.contrib.auth import get_user_model
import re
User = get_user_model()

def rand_str(n=4):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def make_username_from_email(email):
    email_parts = email.split("@")
    username = email_parts[0][:len(email_parts[0])//2]
    username = re.sub(r'\W+', '', username)
    
    if not username:
        username = "user"
    username += ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=4))
    while User.objects.filter(username=username).exists():
        username = f"{username[:-4]}_{random.randint(1, 9999)}"
    
    return username

def make_random_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    return "".join(random.choices(chars, k=length))
