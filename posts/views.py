from rest_framework import status, filters, generics
from django.contrib.auth.decorators import permission_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .serializers import (
    PostSerializer,
    TagSerializer,
    CommentSerializer,
    ReplySerializer,
    UserSearchSerializer,
    PostSearchSerializer,
    LikeCountPostSerializer,
    LikeCountCommentSerializer,
)
from django.db import models
from users.models import CustomUser as User
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.contrib.postgres.search import SearchVector, TrigramSimilarity
from django.shortcuts import get_object_or_404
from .models import Post, Comment, Tag
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter, OpenApiTypes,extend_schema_view
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from django.core.cache import cache
from .cache import *
import logging
import time
log = logging.getLogger(__name__)



class PostListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PostSerializer

    @extend_schema(
        summary="List all posts",
        description="Return a list of all posts.",
        responses={200: PostSerializer(many=True)},
        tags=["Posts"],
    )
    # def get(self, request):
    #     posts = Post.objects.all()
    #     serializer = PostSerializer(posts, many=True)
    #     return Response(serializer.data)

    # def get(self, request):
    #     # 1. Generate the predictable cache key
    #     cache_key = key_posts_list()
        
    #     # 2. Try to get the data from the cache first
    #     cached_data = cache.get(cache_key)

    #     # 3. Cache Hit: If data is found, return it immediately
    #     if cached_data is not None:
    #         print("Serving posts list from CACHE!") # For debugging
    #         return Response(cached_data)

    #     # 4. Cache Miss: If no data, query the database
    #     print("Serving posts list from DATABASE.") # For debugging
    #     posts = Post.objects.all()
    #     serializer = PostSerializer(posts, many=True)
        
    #     # 5. Store the new data in the cache for next time
    #     cache.set(cache_key, serializer.data, timeout=None) # timeout in seconds

    #     return Response(serializer.data)


    # p2p_backend/posts/views.py

    def get(self, request):
        cache_key = key_posts_list()
        print("cache_key", cache_key)
        cached_data = cache_get(cache_key)

        if cached_data is not None:
            print("Serving posts list from CACHE!") 
            return Response(cached_data)

        print("Serving posts list from DATABASE.")
        
        # --- THIS IS THE FIX ---
        # Optimize the queryset BEFORE it goes to the serializer
        posts = Post.objects.select_related("author").prefetch_related("tags", "mentions").all()
        # ----------------------
        
        serializer = PostSerializer(posts, many=True)
        
        # cache_set(cache_key, serializer.data, timeout=None)
        cache_set(cache_key, serializer.data, timeout=None)

        return Response(serializer.data)

    @extend_schema(
        summary="Create a new post",
        description="Create a new post with associated tags.",
        request=PostSerializer,
        responses={
            201: OpenApiResponse(description="Post created successfully."),
            400: OpenApiResponse(description="Validation error"),
        },
        tags=["Posts"],
        examples=[
            OpenApiExample(
                "Example request",
                value={
                    "title": "My First Post",
                    "content": "This is the content of my first post.",
                    "tags": ["django", "rest"],
                },
                request_only=True,
                response_only=False,
            )
        ],
    )
    def post(self, request):
        serializer = PostSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # tags = request.data.get("tags", [])
            # for tag in tags:
            #     Tag.objects.get_or_create(name=tag)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostDetailView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PostSerializer

    @extend_schema(
        summary="Retrieve a post",
        description="Retrieve a post identified by slug.",
        responses={
            200: PostSerializer,
            404: OpenApiResponse(description="Post not found"),
        },
        tags=["Posts"],
    )
    # def get(self, request, slug):
    #     try:
    #         post = Post.objects.get(slug=slug)
    #     except Post.DoesNotExist:
    #         return Response(status=status.HTTP_404_NOT_FOUND)
    #     serializer = PostSerializer(post)
    #     return Response(serializer.data)

    def get(self, request, slug):
        cache_key = key_post_detail(slug)

        caches_data = cache_get(cache_key)

        if caches_data is not None:
            print("Serving post detail from CACHE!") # For debugging
            return Response(caches_data)

        print("Serving post detail from DATABASE.") # For debugging
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = PostSerializer(post)
        cache_set(cache_key, serializer.data, POSTS_TTL) # timeout in seconds
        return Response(serializer.data)

    @extend_schema(
        summary="Update a post",
        description="Update a post identified by slug.",
        request=PostSerializer,
        responses={
            200: OpenApiResponse(description="Post updated successfully."),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Post not found"),
        },
        tags=["Posts"],
    )
    def put(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = PostSerializer(post, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        summary="Delete a post",
        description="Delete a post identified by slug if authorized.",
        responses={
            204: OpenApiResponse(description="Post deleted successfully."),
            403: OpenApiResponse(description="Not authorized to delete this post."),
            404: OpenApiResponse(description="Post not found"),
        },
        tags=["Posts"],
    )
    def delete(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if request.user == post.author or request.user.is_staff:
            post.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"detail": "Not authorized to delete this post."},
            status=status.HTTP_403_FORBIDDEN,
        )


class ListTags(APIView):
    permission_classes = [IsAdminUser]
    serializer_class = TagSerializer

    @extend_schema(
        summary="List all tags",
        description="Return a list of all tags.",
        responses={200: TagSerializer(many=True)},
        tags=["Tags"],
        examples=[
            OpenApiExample(
                "Example response",
                value=[{"name": "Django", "slug": "django"}],
                response_only=True,
            )
        ],
    )
    def get(self, request, slug=None):
        if slug:
            try:
                tag = Tag.objects.get(slug=slug)
                serializer = PostSerializer(tag)
                return Response(serializer.data)
            except Tag.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
        else:
            tags = Tag.objects.all()
            serializer = PostSerializer(tags, many=True)
            return Response(serializer.data)


class TagView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TagSerializer

    def post(self, request):
        serializer = TagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @permission_required("is_admin", raise_exception=True)
    def delete(self, request, slug):
        try:
            tag = Tag.objects.get(slug=slug)
        except Tag.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        tag.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostCommentsView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer
    
    @extend_schema(
        summary="Create a comment on a post",
        description="Add a comment to the post identified by slug.",
        request=CommentSerializer,
        responses={
            201: OpenApiResponse(description="Comment created successfully."),
            400: OpenApiResponse(description="Validation error"),
        },
        tags=["Comments"],
        examples=[
            OpenApiExample(
                "Example request",
                value={"content": "This is a comment.", "parent": None},
                request_only=True,
                response_only=False,
            )
        ],
    )
    def post(self, request, slug):
        # Create comment for post identified by slug
        data = request.data.copy()
        # Assign post id from slug
        post = get_object_or_404(Post, slug=slug)
        data['post'] = post.id
        serializer = CommentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
from .serializers import CommentUpdateSerializer
class CommentUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    # serializer_class = CommentUpdateSerializer

    @extend_schema(
        summary="Update a comment",
        description="Update a comment identified by slug.",
        request=CommentUpdateSerializer,
        responses={
            200: OpenApiResponse(description="Comment updated successfully."),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Comment not found"),
        },
        tags=["Comments"],
    )
    def put(self, request, slug):
        try:
            comment = Comment.objects.get(slug=slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommentUpdateSerializer(comment, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class CommentDetailView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer

    def get_object(self, slug):
        return get_object_or_404(Comment, slug=slug)

    @extend_schema(
        summary="Retrieve a comment",
        description="Fetch comment details by comment slug.",
        responses={200: CommentSerializer, 404: OpenApiResponse(description="Comment not found")},
        tags=["Comments"],
    )
    def get(self, request, slug):
        try:
            comment = self.get_object(slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommentSerializer(comment)
        return Response(serializer.data)

    @extend_schema(
        summary="Update a comment",
        description="Update a comment identified by slug.",
        request=CommentSerializer,
        responses={
            200: OpenApiResponse(description="Comment updated successfully."),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Comment not found"),
        },
        tags=["Comments"],
    )
    def put(self, request, slug):
        try:
            comment = self.get_object(slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommentSerializer(comment, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

  

class DeleteCommentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete a comment",
        description="Delete a comment by slug if the requesting user is the author or staff.",
        responses={
            204: OpenApiResponse(description="Comment deleted successfully."),
            403: OpenApiResponse(description="Not authorized to delete this comment."),
            404: OpenApiResponse(description="Comment not found"),
        },
        tags=["Comments"],
    )
    def delete(self, request, slug):
        comment = get_object_or_404(Comment, slug=slug)
        if request.user == comment.author or request.user.is_staff:
            comment.delete()
            return Response({"detail": "Comment deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Not authorized to delete this comment."}, status=status.HTTP_403_FORBIDDEN)

class CommentCountView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get the count of comments of a particular post",
        responses={200: OpenApiResponse(description="Count of comments")},
        tags=["Comments"],
        examples=[
            OpenApiExample(
                "Example response",
                value={"count": 10},
                response_only=True,
            )
        ],
    )
    def get(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response(
                {"detail": "Post not found"}, status=status.HTTP_404_NOT_FOUND
            )

        count = Comment.objects.filter(post=post).count()
        return Response({"count": count})


class ListCommentsPost(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer

    @extend_schema(
        summary="List all parent comments for a post",
        description="Return all top-level comments (parent is null) for a post identified by slug.",
        responses={
            200: CommentSerializer(many=True),
            404: OpenApiResponse(description="Post not found"),
        },
        tags=["Comments"],
        examples=[
            OpenApiExample(
                "Example response",
                value=[
                    {
                        "content": "This is a top-level comment.",
                        "post": 1,
                        "parent": None,
                        "slug": "comment-slug",
                    }
                ],
                response_only=True,
            )
        ],
    )
    def get(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response({"detail": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
        comments = Comment.objects.filter(post=post, parent__isnull=True)
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)


class ListCreateCommentReplies(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReplySerializer

    @extend_schema(
        summary="List all replies to a comment",
        description="Return all reply comments for a comment identified by slug.",
        responses={200: ReplySerializer(many=True), 404: OpenApiResponse(description="Comment not found")},
        tags=["Comments"],
    )
    def get(self, request, slug):
        try:
            comment = Comment.objects.get(slug=slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        replies = comment.replies.all()  # uses related_name='replies'
        serializer = ReplySerializer(replies, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a reply to a comment",
        description="Create a reply for a specific comment identified by slug.",
        request=ReplySerializer,
        responses={201: ReplySerializer, 404: OpenApiResponse(description="Comment not found")},
        tags=["Comments"],
    )
    def post(self, request, slug):
        try:
            parent_comment = Comment.objects.get(slug=slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReplySerializer(
            data=request.data,
            context={"request": request, "parent_comment": parent_comment},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, slug):
        try:
            comment = Comment.objects.get(slug=slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        comment.delete()
        return Response({"detail": "Comment deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class LikesCountPost(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LikeCountPostSerializer

    @extend_schema(
        summary="Get the count of likes for a post",
        responses={200: LikeCountPostSerializer, 404: OpenApiResponse(description="Post not found")},
        tags=["Likes"],
    )
    def get(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response({"detail": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        count = post.likes.count()
        is_like = post.likes.filter(id=request.user.id).exists()
        return Response({"count": count, "is_like": is_like})


class LikeCountComment(APIView):
    permission_classes = [IsAuthenticated]
    serializers_class = LikeCountCommentSerializer

    @extend_schema(
        summary="Get the count of likes for a comment",
        responses={200: LikeCountCommentSerializer, 404: OpenApiResponse(description="Comment not found")},
        tags=["Likes"],
    )
    def get(self, request, slug):
        try:
            comment = Comment.objects.get(slug=slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        count = comment.likes.count()
        is_like = comment.likes.filter(id=request.user.id).exists()
        return Response({"count": count, "is_like": is_like})
    
# ---- Quick inline serializers for responses ----
class SimpleDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()

class CountResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    is_like = serializers.BooleanField(required=False)



# ---- Likes ----
class LikePost(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SimpleDetailSerializer

    @extend_schema(
        summary="Like a post",
        responses={200: SimpleDetailSerializer, 404: OpenApiResponse(description="Post not found")},
        tags=["Likes"],
    )
    def put(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response({"detail": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
        post.likes.add(request.user)
        return Response({"detail": "Post liked successfully"}, status=status.HTTP_200_OK)
    
class UnlikePost(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SimpleDetailSerializer

    @extend_schema(
        summary="Unlike a post",
        responses={
            200: SimpleDetailSerializer,
            400: SimpleDetailSerializer,
            404: OpenApiResponse(description="Post not found"),
        },
        tags=["Likes"],
    )
    def put(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response({"detail": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        if not post.likes.filter(id=request.user.id).exists():
            return Response({"detail": "You have not liked this post."}, status=status.HTTP_400_BAD_REQUEST)

        post.likes.remove(request.user)
        return Response({"detail": "Post unliked successfully"}, status=status.HTTP_200_OK)
    
class UnlikeComment(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SimpleDetailSerializer

    @extend_schema(
        summary="Unlike a comment",
        responses={
            200: SimpleDetailSerializer,
            400: SimpleDetailSerializer,
            404: OpenApiResponse(description="Comment not found"),
        },
        tags=["Likes"],
        
    )

    def put(self, request, slug):
        try:
            comment = Comment.objects.get(slug=slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        if not comment.likes.filter(id=request.user.id).exists():
            return Response({"detail": "You have not liked this comment."}, status=status.HTTP_400_BAD_REQUEST)

        comment.likes.remove(request.user)
        return Response({"detail": "Comment unliked successfully"}, status=status.HTTP_200_OK)

class LikeComment(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SimpleDetailSerializer

    @extend_schema(
        summary="Like a comment",
        responses={200: SimpleDetailSerializer, 404: OpenApiResponse(description="Comment not found")},
        tags=["Likes"],
    )
    def put(self, request, slug):
        try:
            comment = Comment.objects.get(slug=slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)
        if(comment.likes.filter(id=request.user.id).exists()):
            comment.likes.remove(request.user)
            return Response({"detail": "Comment unliked successfully"}, status=status.HTTP_200_OK)
        comment.likes.add(request.user)
        return Response({"detail": "Comment liked successfully"}, status=status.HTTP_200_OK)



class SearchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Unified search for users or posts",
        parameters=[
            OpenApiParameter(
                name="q",
                type=OpenApiTypes.STR,
                required=True,
                description="Search query string"
            ),
            OpenApiParameter(
                name="type",
                type=OpenApiTypes.STR,
                required=False,
                enum=["people", "posts"],
                description="Type of search: 'people' or 'posts' (default: posts)"
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=UserSearchSerializer(many=True),
                description="List of users (if type=people)"
            ),
            201: OpenApiResponse(
                response=PostSearchSerializer(many=True),
                description="List of posts (if type=posts)"
            ),
            400: SimpleDetailSerializer,
        },
        tags=["Search"],
    )
    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', None)
        search_type = request.query_params.get('type', 'posts')

        if not query:
            return Response({"detail": "A search query parameter 'q' is required."}, status=400)

        if search_type == 'people':
            queryset = User.objects.annotate(
                similarity=TrigramSimilarity('username', query),
            ).filter(similarity__gt=0.3).order_by('-similarity')
            serializer = UserSearchSerializer(queryset, many=True)
            return Response(serializer.data)

        elif search_type == 'posts':
            queryset = Post.objects.filter(published=True).annotate(
                similarity=TrigramSimilarity(
                    Concat('title', Value(' '), 'content', output_field=models.TextField()),
                    query
                ),
                search=SearchVector('title', 'content'),
            ).filter(
                Q(search=query) | Q(similarity__gt=0.3)
            ).order_by('-similarity')
            serializer = PostSearchSerializer(queryset, many=True)
            return Response(serializer.data)

        return Response({"detail": f"Invalid search type '{search_type}'. Use 'people' or 'posts'."}, status=400)
    


class UserSearchAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchSerializer
    queryset = User.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'full_name']

    @extend_schema(
        summary="Search all users",
        description="Return a list of all users matched with the search query.",
        responses={200: UserSearchSerializer(many=True)},
        tags=["Search"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
   



@extend_schema_view(
    get=extend_schema(
        summary="Search for tags",
        description="Search and return tags by query string.",
        parameters=[
            OpenApiParameter(
                name="q",
                location=OpenApiParameter.QUERY,
                required=True,
                type=OpenApiTypes.STR,
                description="Search query string",
            )
        ],
        responses={
            200: OpenApiResponse(response=TagSerializer(many=True)),
            400: OpenApiResponse(response=SimpleDetailSerializer),
        },
        tags=["Search"],
    )
)
class TagSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializers_class = TagSerializer

    def get(self, request, *args, **kwargs):
        tag_name = request.query_params.get("q")
        if not tag_name:
            return Response(
                {"detail": "A search query parameter 'q' is required."},
                status=400,
            )
        post = Post.objects.filter(tags__name__icontains=tag_name)
        serializer = PostSerializer(post, many=True)
        return Response(serializer.data)
