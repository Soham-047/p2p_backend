from rest_framework import status
from django.contrib.auth.decorators import permission_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .serializers import (
    PostSerializer,
    TagSerializer,
    CommentSerializer,
)
from django.shortcuts import get_object_or_404
from .models import Post, Comment, Tag
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample




class PostListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PostSerializer

    @extend_schema(
        summary="List all posts",
        description="Return a list of all posts.",
        responses={200: PostSerializer(many=True)},
        tags=["Posts"],
    )
    def get(self, request):
        posts = Post.objects.all()
        serializer = PostSerializer(posts, many=True)
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
                    "author": 1,
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
    def get(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = PostSerializer(post)
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
                value={"content": "This is a comment.", "parent": None, "author": 1},
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


class ListCommentReplies(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CommentSerializer

    @extend_schema(
        summary="List all replies to a comment",
        description="Return all reply comments for a comment identified by slug.",
        responses={
            200: CommentSerializer(many=True),
            404: OpenApiResponse(description="Comment not found"),
        },
        tags=["Comments"],
        examples=[
            OpenApiExample(
                "Example response",
                value=[
                    {
                        "content": "This is a reply comment.",
                        "post": 1,
                        "parent": "comment-slug",
                        "slug": "reply-slug",
                    }
                ],
                response_only=True,
            )
        ],
    )
    def get(self, request, slug):
        try:
            comment = Comment.objects.get(slug=slug)
        except Comment.DoesNotExist:
            return Response({"detail": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)
        replies = Comment.objects.filter(parent=comment)
        serializer = CommentSerializer(replies, many=True)
        return Response(serializer.data)


class LikesCount(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get the count of likes for a comment",
        responses={200: OpenApiResponse(description="Count of likes")},
        tags=["Likes"],
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
        count = post.likes.count()
        return Response({"count": count})
    
class LikePost(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Like a post",
        responses={200: OpenApiResponse(description="Post liked successfully")},
        tags=["Likes"],
        
    )
    def put(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response({"detail": "Post not found"},status=status.HTTP_404_NOT_FOUND)
        post.likes.add(request.user)
        return Response({"detail": "Post liked successfully"},status=status.HTTP_200_OK)
    
class UnlikePost(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Unlike a post",
        responses={
            200: OpenApiResponse(description="Post unliked successfully"),
            400: OpenApiResponse(description="User has not liked this post"),
            404: OpenApiResponse(description="Post not found"),
        },
        tags=["Likes"],
    )
    def put(self, request, slug):
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not post.likes.filter(id=request.user.id).exists():
            return Response(
                {"detail": "You have not liked this post."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        post.likes.remove(request.user)
        return Response({"detail": "Post unliked successfully"},status=status.HTTP_200_OK)
