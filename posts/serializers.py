# posts/serializers.py
from rest_framework import serializers
from .models import Post, Comment, Tag, Media
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

class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = ['url', 'media_type', 'display_order']


class PostSerializer(serializers.ModelSerializer):
    # --- For READING data (output) ---
    author_full_name = serializers.CharField(source='author.full_name', read_only=True)
    author_username = serializers.ReadOnlyField(source='author.username')
    avatar_url = serializers.SerializerMethodField()
    headline = serializers.SerializerMethodField()
    slug = serializers.CharField(read_only=True)
    mentions = UserMentionSerializer(many=True, read_only=True)
    tag_names = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="name", source="tags"
    )
    # The 'source' argument has been removed from this line.
    media_items = MediaSerializer(many=True, read_only=True)
    comment_count = serializers.IntegerField(read_only=True) # Added from previous step
    likes_count = serializers.IntegerField(read_only=True)
    # --- For WRITING data (input) ---
    tags = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    media_data = serializers.ListField(
        child=serializers.DictField(), required=False, write_only=True
    )

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'content', 'published', 'created_at', 'updated_at',
            'author_full_name', 'author_username', 'avatar_url', 'headline',
            'mentions', 'tag_names','comment_count','likes_count', 'tags', 'media_items', 'media_data'
        ]
        read_only_fields = ['author']

    def get_avatar_url(self, obj) -> str:
        profile = getattr(obj.author, 'profile', None)
        if profile and profile.avatar_url:
            return profile.avatar_url
        return None

    def get_headline(self, obj) -> str:
        profile = getattr(obj.author, 'profile', None)
        if profile:
            return profile.headline
        return None

    # def create(self, validated_data):
    #     user = self.context['request'].user
    #     tags_data = validated_data.pop('tags', [])
    #     media_data = validated_data.pop('media_data', [])
        
    #     post = Post.objects.create(author=user, **validated_data)

    #     for tag_name in tags_data:
    #         tag, _ = Tag.objects.get_or_create(name=tag_name)
    #         post.tags.add(tag)
        
    #     for index, media_item in enumerate(media_data):
    #         Media.objects.create(
    #             post=post,
    #             url=media_item.get('url'),
    #             media_type=media_item.get('media_type'),
    #             display_order=index
    #         )
        
    #     mentioned_usernames = re.findall(r'@(\w+)', validated_data['content'])
    #     if mentioned_usernames:
    #         mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
    #         post.mentions.set(mentioned_users)
        
    #     return post


    def create(self, validated_data):
        user = self.context['request'].user
        tags_data = validated_data.pop('tags', [])
        media_data = validated_data.pop('media_data', [])
        content = validated_data.get('content', '')

        # 1. Create the main Post object
        post = Post.objects.create(author=user, **validated_data)

        # 2. Handle Tags in Bulk
        if tags_data:
            # Find which tags already exist in a single query
            existing_tags = Tag.objects.filter(name__in=tags_data)
            existing_tag_names = {t.name for t in existing_tags}
            
            # Determine which tags are new
            new_tag_names = [name for name in tags_data if name not in existing_tag_names]
            
            # Create all new tags in a single bulk query
            if new_tag_names:
                new_tags = [Tag(name=name) for name in new_tag_names]
                Tag.objects.bulk_create(new_tags)
            
            # Set all tags for the post
            all_tags = Tag.objects.filter(name__in=tags_data)
            post.tags.set(all_tags)

        # 3. Handle Media in Bulk
        if media_data:
            # Create Media objects in memory first
            media_objects_to_create = [
                Media(
                    post=post,
                    url=item.get('url'),
                    media_type=item.get('media_type'),
                    display_order=index
                ) for index, item in enumerate(media_data)
            ]
            # Create all media items in a single bulk query
            Media.objects.bulk_create(media_objects_to_create)

        # 4. Handle Mentions (this part was already efficient)
        mentioned_usernames = re.findall(r'@(\w+)', content)
        if mentioned_usernames:
            mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
            post.mentions.set(mentioned_users)
        
        # Manually set comment_count for the response, as a new post has 0 comments
        post.comment_count = 0
        post.likes_count = 0
        post.refresh_from_db()
        return post

    # def update(self, instance, validated_data):
    #     tags_data = validated_data.pop('tags', None)
    #     media_data = validated_data.pop('media_data', None)

    #     instance = super().update(instance, validated_data)

    #     if tags_data is not None:
    #         instance.tags.clear()
    #         for tag_name in tags_data:
    #             tag, _ = Tag.objects.get_or_create(name=tag_name)
    #             instance.tags.add(tag)

    #     if media_data is not None:
    #         instance.media_items.all().delete()
    #         for index, media_item in enumerate(media_data):
    #             Media.objects.create(
    #                 post=instance,
    #                 url=media_item.get('url'),
    #                 media_type=media_item.get('media_type'),
    #                 display_order=index
    #             )

    #     content = validated_data.get('content', instance.content)
    #     mentioned_usernames = re.findall(r'@(\w+)', content)
    #     if mentioned_usernames:
    #         mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
    #         instance.mentions.set(mentioned_users)
    #     else:
    #         instance.mentions.clear()
        
    #     return instance


    def update(self, instance, validated_data):
    # Pop relational data to handle it separately
        tags_data = validated_data.pop('tags', None)
        media_data = validated_data.pop('media_data', None)

        # 1. Update the Post instance with simple fields
        instance = super().update(instance, validated_data)

        # 2. Handle Tags update in Bulk
        if tags_data is not None:
            # Find existing tags from the provided list in one query
            existing_tags = Tag.objects.filter(name__in=tags_data)
            existing_tag_names = {t.name for t in existing_tags}

            # Determine which tags are new and need to be created
            new_tag_names = [name for name in tags_data if name not in existing_tag_names]
            
            # Create all new tags in a single bulk query
            if new_tag_names:
                new_tags_to_create = [Tag(name=name) for name in new_tag_names]
                Tag.objects.bulk_create(new_tags_to_create)
            
            # Get a queryset of all tags (existing + newly created) for the post
            all_tags = Tag.objects.filter(name__in=tags_data)
            # Use .set() to efficiently update the relation in one go
            instance.tags.set(all_tags)

        # 3. Handle Media update in Bulk
        if media_data is not None:
            # First, delete all existing media items for the post in one query
            instance.media_items.all().delete()
            
            # Then, bulk-create the new media items
            media_objects_to_create = [
                Media(
                    post=instance,
                    url=item.get('url'),
                    media_type=item.get('media_type'),
                    display_order=index
                ) for index, item in enumerate(media_data)
            ]
            # Check if there's anything to create before hitting the DB
            if media_objects_to_create:
                Media.objects.bulk_create(media_objects_to_create)

        # 4. Handle Mentions update (only if content was updated)
        if 'content' in validated_data:
            content = validated_data.get('content', '')
            mentioned_usernames = re.findall(r'@(\w+)', content)
            
            if mentioned_usernames:
                mentioned_users = CustomUser.objects.filter(username__in=mentioned_usernames)
                instance.mentions.set(mentioned_users)
            else:
                # If the updated content has no mentions, clear the relation
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


