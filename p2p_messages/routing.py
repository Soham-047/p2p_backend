from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path
from django.core.asgi import get_asgi_application
from p2p_messages import consumers

django_asgi_app = get_asgi_application()

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<username>[\w.@+-]+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/test/$", consumers.ChatConsumer.as_asgi()),
]

# application = ProtocolTypeRouter({
#     'http': django_asgi_app,
#     'websocket': AuthMiddlewareStack(
#         URLRouter(
#             websocket_urlpatterns
#         )
#     ),
# })
