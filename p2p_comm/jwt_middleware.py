import jwt
from django.conf import settings
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from urllib.parse import parse_qs
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "p2p_comm.settings")

app = Celery("p2p_comm")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Lazy import so Django apps are ready
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.auth import get_user_model

        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token_list = query_params.get("token", [])

        token = token_list[0] if token_list else None

        if token:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = payload.get("user_id")

                User = get_user_model()
                user = await database_sync_to_async(User.objects.get)(id=user_id)
                scope["user"] = user
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist):
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
