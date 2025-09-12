import re
from django.db import models
from users.models import CustomUser
from django.utils.text import slugify
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug or self.slug == '':
            base_slug = slugify(self.name)
            unique_slug = base_slug
            counter = 1
            while Tag.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True,blank=True)
    content = models.TextField()
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=True)
    tags = models.ManyToManyField(Tag, blank=True)
    likes = models.ManyToManyField(CustomUser, related_name='liked_posts', blank=True)
    mentions = models.ManyToManyField(CustomUser, related_name='mentioned_posts', blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.author}"
    
    def save(self, *args, **kwargs):
        if not self.slug or self.slug == '':
            base_slug = slugify(self.title)
            unique_slug = base_slug
            counter = 1
            while Post.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

        mentioned_usersnames = re.findall(r'@(\w+)', self.content)
        if mentioned_usersnames:
            mentioned_user = CustomUser.objects.filter(username__in=mentioned_usersnames)
            self.mentions.set(mentioned_user)
        else:
            self.mentions.clear()

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='replies', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    likes = models.ManyToManyField(CustomUser, related_name='liked_comments', blank=True)
    slug = models.SlugField(blank=True,unique=True)
    mentions = models.ManyToManyField(CustomUser, related_name='mentioned_comments', blank=True)
    
    def __str__(self):
        return f"Comment by {self.author} on {self.post}"
    
    def save(self, *args, **kwargs):
        if not self.slug or self.slug == '':
            # Use a shortened, slugified part of content as base slug
            base_slug = slugify(self.content[:50])  # first 50 chars of content
            unique_slug = base_slug
            counter = 1
            # Check for uniqueness among Comments, exclude self when updating
            while Comment.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

        mentioned_usersnames = re.findall(r'@(\w+)', self.content)
        if mentioned_usersnames:
            mentioned_user = CustomUser.objects.filter(username__in=mentioned_usersnames)
            self.mentions.set(mentioned_user)
        else:
            self.mentions.clear()


class Media(models.Model):
    """
    Represents a single media item (image or video) linked to a post.
    """
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    # Foreign Key to the Post model.
    # If a Post is deleted, all its associated media will be deleted too (CASCADE).
    # `related_name` lets you access media from a post instance, e.g., `my_post.media_items.all()`
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='media_items')
    
    # The URL provided by Cloudinary
    url = models.URLField(max_length=500)
    
    # To differentiate between images and videos
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)
    
    # An integer to maintain the order of media items in a post (e.g., 1, 2, 3...)
    display_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Default ordering to ensure media is retrieved in the correct sequence
        ordering = ['display_order']

    def __str__(self):
        return f"{self.get_media_type_display()} for post: {self.post.title} by {self.post.author} has slug {self.post.slug}"