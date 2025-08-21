from posts.models import (
    Post,
    Comment,
    Tag,
)

from users.models import (
    CustomUser, 
)
from rest_framework import serializers
from django.utils.text import slugify


class PostSerializer(serializers.ModelSerializer):
    # Optionally declare tags to help input validation (not strictly required)
    tags = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        write_only=True   # Write only; output handled in to_representation
    )

    class Meta:
        model = Post
        fields = ['title', 'content', 'slug', 'tags']  # 'tags' here refers to input ListField
        read_only_fields = ['slug']

    def validate_author(self, value):
        if not isinstance(value, CustomUser):
            raise serializers.ValidationError("Author must be a user")
        return value

    def validate(self, data):
        # Generate unique slug if not provided
        if not data.get('slug'):
            base_slug = slugify(data.get('title', ''))
            unique_slug = base_slug
            counter = 1
            while Post.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            data['slug'] = unique_slug
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
        instance.title = validated_data.get('title', instance.title)
        instance.content = validated_data.get('content', instance.content)
        instance.save()
        if tags_data is not None:
            instance.tags.clear()
            for tag_name in tags_data:
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                instance.tags.add(tag)
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Output tag names as list
        rep['tags'] = [tag.name for tag in instance.tags.all()]
        return rep

    

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"

    def validate(self, data):
        # Generate slug from title if not provided or empty
        if not data.get('slug'):
            base_slug = slugify(data.get('name', ''))
            unique_slug = base_slug
            counter = 1
            # Check uniqueness
            while Tag.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            data['slug'] = unique_slug
        return data

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = "__all__"

        