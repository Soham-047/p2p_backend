# posts/serializers.py
from rest_framework import serializers
from .models import Post, Comment, Tag
from users.models import CustomUser
from django.utils.text import slugify


class UserMentionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['username', 'full_name']
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["name", "slug"]

    def validate(self, data):
        if not data.get("slug"):
            base_slug = slugify(data.get("name", ""))
            unique_slug = base_slug
            counter = 1
            while Tag.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            data["slug"] = unique_slug
        return data

class PostSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    tag_names = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="name", source="tags"
    )
    author = serializers.CharField(source='author.full_name', read_only=True)
    slug = serializers.CharField(read_only=True)
    mentions = UserMentionSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ['title', 'content', 'slug', "tags", 'tag_names', 'author','mentions', 'published', 'created_at', 'updated_at']
        read_only_fields = ['slug', 'author', 'created_at', 'updated_at']

    def validate(self, data):
        # slug auto-generation handled in model; nothing special required here
        return data

    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        user = self.context['request'].user
        post = Post.objects.create(author=user, **validated_data)
        for tag_name in tags_data:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            post.tags.add(tag)
        return post

    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if tags_data is not None:
            instance.tags.clear()
            for tag_name in tags_data:
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                instance.tags.add(tag)
        return instance

class CommentSerializer(serializers.ModelSerializer):
    # author = serializers.CharField(source='author.full_name', read_only=True)
    author = serializers.SerializerMethodField()
    post = serializers.PrimaryKeyRelatedField(queryset=Post.objects.all(), required=True)
    mentions = UserMentionSerializer(many=True, read_only=True)

    class Meta:
        model = Comment
        fields = "__all__"
        read_only_fields = ["slug", "author", "created_at", "updated_at"]

    def get_author(self, obj):
        if obj.author and hasattr(obj.author, 'full_name'):
            return obj.author.full_name
        return None

class CommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['content']
        read_only_fields = ["slug", "author", "created_at", "updated_at"]

class ReplySerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.full_name", read_only=True)
    parent_author = serializers.CharField(source="parent.author.full_name", read_only=True)

    class Meta:
        model = Comment
        fields = ["slug", "content", "author", "parent_author", "post", "created_at", "updated_at"]
        read_only_fields = ["slug", "author", "parent", "post", "created_at", "updated_at"]

    def create(self, validated_data):
        parent_comment = self.context["parent_comment"]
        reply = Comment.objects.create(
            parent=parent_comment,
            post=parent_comment.post,
            author=self.context["request"].user,
            content=validated_data["content"],
        )
        print(parent_comment.author.full_name)
        return reply

# search/serializers.py


import base64
from django.urls import reverse
class UserSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for representing users in search results.
    """
    avatar = serializers.SerializerMethodField()
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'full_name', 'avatar']

    def get_avatar(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile and profile.avatar_blob:
            # return f"data:{profile.avatar_content_type};base64,{base64.b64encode(profile.avatar_blob).decode()}"
            return self.context["request"].build_absolute_uri(
                reverse("profile-avatar", args=[obj.id])
            )
        return None
class PostSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for representing posts in search results.
    The 'tags' field has been removed.
    """
    author = UserSearchSerializer(read_only=True)

    class Meta:
        model = Post
        fields = ['title', 'slug', 'author', 'created_at']

class LikeCountPostSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    is_like = serializers.BooleanField()

class LikeCountCommentSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    is_like = serializers.BooleanField()


# class TagSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Tag
#         fields = ['name']