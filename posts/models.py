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