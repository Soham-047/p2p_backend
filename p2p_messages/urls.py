# chatapp/urls.py
from django.urls import path
from .views import MessageListCreateAPIView, DecryptMessageView, ChatHistoryView

urlpatterns = [
    path('messages/', MessageListCreateAPIView.as_view(), name='message-list-create'),
    path('decrypt/', DecryptMessageView.as_view(), name='decrypt_message'),
    path('history/<str:username>/', ChatHistoryView.as_view(), name='chat_history'),
]
