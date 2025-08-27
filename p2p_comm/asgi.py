import os
from p2p_comm.jwt_middleware import JWTAuthMiddleware
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'p2p_comm.settings')

django_asgi_app = get_asgi_application()

from p2p_messages.routing import websocket_urlpatterns  # use your actual app name & routing file

application = ProtocolTypeRouter({
    "http": django_asgi_app,  # Handles traditional HTTP requests
    "websocket": JWTAuthMiddleware(  # Handles WebSocket connections with auth
        URLRouter(
            websocket_urlpatterns  # WebSocket URL patterns from routing.py in your app
        )
    ),
})
