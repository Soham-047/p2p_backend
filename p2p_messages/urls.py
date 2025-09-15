# chatapp/urls.py
from django.urls import path
from .views import MessageListCreateAPIView, DecryptMessageView, ChatHistoryView,RecentChatsAPIView, unread_counts, mark_read, OldChatHistoryView

urlpatterns = [
    path('messages/', MessageListCreateAPIView.as_view(), name='message-list-create'),
    path('decrypt/', DecryptMessageView.as_view(), name='decrypt_message'),
    path('history/<str:username>/', ChatHistoryView.as_view(), name='chat_history'),
    path('chats/recent/', RecentChatsAPIView.as_view(), name='recent-chats'),
    path("api/unread/", unread_counts),
    path("api/unread/mark-read/", mark_read),
    path('chat/<str:username>/old-history/', OldChatHistoryView.as_view(), name='chat-history'),

]
