from django.urls import path
from .views import (
    PostListCreateView,
    PostDetailView,
    PostCommentsView,
    CommentDetailView,
    ListCommentsPost,
    ListTags,
    DeleteCommentView,
    CommentCountView,
    LikesCount,
    LikePost,
    UnlikePost,
    ListCreateCommentReplies,
    LikeComment,
    SearchView,
)

urlpatterns = [
    # POSTs
    path('posts/', PostListCreateView.as_view(), name='post-list-create'),
    path('posts/<slug:slug>/', PostDetailView.as_view(), name='post-detail'),

    # COMMENTS - List & Create for a Post
    path('<slug:slug>/comments/', PostCommentsView.as_view(), name='post-comments'),

    # COMMENT - Detail, Update, Delete by Comment Slug
    path('comments/<slug:slug>/', CommentDetailView.as_view(), name='comment-detail'),

    # COMMENTS - Parent comments for a post
    path('list-comments/<slug:slug>/', ListCommentsPost.as_view(), name='list-comments'),

    
    # COMMENTS - Count comments (across all or filtered by post)
    path('count-comments/<slug:slug>/', CommentCountView.as_view(), name='count-comments'),

    # COMMENTS - Delete comment by slug (alternative route)
    path('delete-comment/<slug:slug>/', DeleteCommentView.as_view(), name='delete-comment'),

    # TAGS - Delete tag by slug
    path('delete-tag/<slug:slug>/', ListTags.as_view(), name='delete-tag'),

    #Count Likes for a post
    path('<slug:slug>/like-count/', LikesCount.as_view(), name='post-like-count'),
    
    #Like a Post
    path('<slug:slug>/like-post/', LikePost.as_view(), name='like-post'),

    #Unlike a post
    path('<slug:slug>/unlike-post/', UnlikePost.as_view(), name='unlike-post'),

    #create and list Reply to a comment
    path("comments/<slug:slug>/replies/", ListCreateCommentReplies.as_view(), name="comment-replies"),

    #Like a comment
    path("comments/<slug:slug>/like/", LikeComment.as_view(), name="like-comment"),

    #urls for search on Posts and Users
    path("search/", SearchView.as_view(), name="search"),
]

