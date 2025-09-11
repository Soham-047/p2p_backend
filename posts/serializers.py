# posts/serializers.py
from rest_framework import serializers
from .models import Post, Comment, Tag
from users.models import CustomUser
from django.utils.text import slugify
import re

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
    author_full_name = serializers.CharField(source='author.full_name', read_only=True)
    avatar_url = serializers.SerializerMethodField()
    headline = serializers.SerializerMethodField()
    author_username = serializers.ReadOnlyField(source='author.username')
    slug = serializers.CharField(read_only=True)
    mentions = UserMentionSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ['title', 'content', 'slug', "tags", 'tag_names', 'author_full_name','author_username', 'avatar_url', 'headline','mentions', 'published', 'created_at', 'updated_at']
        read_only_fields = ['slug', 'author', 'created_at', 'updated_at']

    def validate(self, data):
        # slug auto-generation handled in model; nothing special required here
        return data

    def get_avatar_url(self, obj):
        profile = getattr(obj.author, 'profile', None)
        if profile and profile.avatar_url:
            return profile.avatar_url  # directly return the stored URL
        return None
    
    def get_headline(self, obj):
        profile = getattr(obj.author, 'profile', None)
        if profile:
            return profile.headline
        return None
    
    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        user = self.context['request'].user
        post = Post.objects.create(author=user, **validated_data)

        for tag_name in tags_data:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            post.tags.add(tag)

        mentioned_usernames = re.findall(r'@(\w+)', validated_data['content'])
        if mentioned_usernames:
            mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
            post.mentions.set(mentioned_users)
        else:
            post.mentions.clear()
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

        content = validated_data.get('content', instance.content)
        mentioned_usernames = re.findall(r'@(\w+)', content)
        if mentioned_usernames:
            mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
            instance.mentions.set(mentioned_users)
        else:
            instance.mentions.clear()
        
        return instance

class CommentSerializer(serializers.ModelSerializer):
    author_full_name = serializers.CharField(source='author.full_name', read_only=True)
    avatar_url = serializers.SerializerMethodField()
    headline = serializers.SerializerMethodField()
    author_username = serializers.ReadOnlyField(source='author.username')
    post = serializers.PrimaryKeyRelatedField(queryset=Post.objects.all(), required=True)
    mentions = UserMentionSerializer(many=True, read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "author_username",
            "author_full_name",
            "avatar_url",
            "headline",
            "post",
            "mentions",
            "content",
            "created_at",
            "updated_at",
            "is_active",
            "slug",
            "parent",
            "likes",
        ]
        read_only_fields = [
            "slug",
            "avatar_url",
            "author_full_name",
            "author_username",
            "headline",
            "created_at",
            "updated_at",
        ]

    def get_avatar_url(self, obj):
        profile = getattr(obj.author, "profile", None)
        if profile and profile.avatar_url:
            return profile.avatar_url
        return None

    def get_headline(self, obj):
        profile = getattr(obj.author, "profile", None)
        if profile:
            return profile.headline
        return None

    def create(self, validated_data):
        comment = Comment.objects.create(**validated_data)
        mentioned_usernames = re.findall(r'@(\w+)', validated_data['content'])
        if mentioned_usernames:
            mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
            comment.mentions.set(mentioned_users)
        else:
            comment.mentions.clear()
        return comment


class CommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['content']
        read_only_fields = ["slug", "author", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        # update content
        instance.content = validated_data.get("content", instance.content)
        instance.save()

        # handle mentions
        mentioned_usernames = re.findall(r'@(\w+)', instance.content)
        if mentioned_usernames:
            mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
            instance.mentions.set(mentioned_users)
        else:
            instance.mentions.clear()

        return instance

# import re
# from rest_framework import serializers

class ReplySerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source="author.username")
    author_full_name = serializers.CharField(source="author.full_name", read_only=True)
    avatar_url = serializers.SerializerMethodField()
    headline = serializers.SerializerMethodField()
    parent_author_full_name = serializers.CharField(source="parent.author.full_name", read_only=True)
    parent_author_username = serializers.ReadOnlyField(source="parent.author.username")

    class Meta:
        model = Comment
        fields = [
            "slug",
            "content",
            "author_username",
            "author_full_name",
            "avatar_url",
            "headline",
            "parent_author_full_name",
            "parent_author_username",
            "post",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "slug",
            "author_username",
            "author_full_name",
            "avatar_url",
            "headline",
            "parent_author_full_name",
            "parent_author_username",
            "parent",
            "post",
            "created_at",
            "updated_at",
        ]

    def get_avatar_url(self, obj):
        profile = getattr(obj.author, "profile", None)
        if profile and profile.avatar_url:
            return profile.avatar_url
        return None

    def get_headline(self, obj):
        profile = getattr(obj.author, "profile", None)
        if profile:
            return profile.headline
        return None

    def create(self, validated_data):
        parent_comment = self.context["parent_comment"]
        reply = Comment.objects.create(
            parent=parent_comment,
            post=parent_comment.post,
            author=self.context["request"].user,
            content=validated_data["content"],
        )

        # 🔎 mention detection
        mentioned_usernames = re.findall(r'@(\w+)', validated_data["content"])
        if mentioned_usernames:
            mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
            reply.mentions.set(mentioned_users)
        else:
            reply.mentions.clear()

        return reply


# search/serializers.py


import base64
from django.urls import reverse
class UserSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for representing users in search results.
    """
    # avatar = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    headline = serializers.SerializerMethodField()
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'full_name', 'avatar_url','headline']

    def get_avatar_url(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile and profile.avatar_url:
            return profile.avatar_url  # directly return the stored URL
        return None
    def get_headline(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile and profile.headline:
            return profile.headline  
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