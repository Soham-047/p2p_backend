from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from .models import Post, Comment

from .tasks import (
    invalidate_post_cache,
    warm_posts_list_cache,
    warm_post_detail_cache,
    # on_comment_created,
    # invalidate_post_detail_cache,
)
from celery import chain


# Run sequentially
@receiver(post_save, sender=Post)
def post_saved(sender, instance: Post, created, **kwargs):
    """
    When a post is created or updated:
    - Invalidate its cache
    - Warm up list & detail caches
    """
    chain(
        invalidate_post_cache.s(instance.slug),
        warm_posts_list_cache.s(),
        warm_post_detail_cache.s(instance.slug)
    )()


# @receiver(post_save, sender=Post)
# def post_saved(sender, instance: Post, created, **kwargs):
#     """
#     When a post is created or updated:
#     - Invalidate its cache
#     - Warm up list & detail caches
#     """
#     invalidate_post_cache.delay(instance.slug)
#     warm_posts_list_cache.delay()
#     warm_post_detail_cache.delay(instance.slug)

@receiver(post_delete, sender=Post)
def post_deleted(sender, instance: Post, **kwargs):
    """
    When a post is deleted:
    - Invalidate its cache
    - Warm up the posts list cache
    """
    invalidate_post_cache.delay(instance.slug)
    warm_posts_list_cache.delay()
    warm_posts_list_cache.delay()

@receiver(m2m_changed, sender=Post.tags.through)
def post_tags_changed(sender, instance: Post, action, **kwargs):
    """
    When tags are added/removed from a post:
    - Invalidate post cache
    - Warm up detail cache
    """
    if action in {"post_add", "post_remove", "post_clear"}:
        invalidate_post_cache.delay(instance.slug)
        warm_posts_list_cache.delay()
        warm_post_detail_cache.delay(instance.slug)

# @receiver(post_save, sender=Comment)
# def comment_saved(sender, instance: Comment, created, **kwargs):
#     """
#     When a comment is created:
#     - Trigger background task for cache update
#     """
#     if created:
#         on_comment_created.delay(instance.post.slug)

# @receiver(post_delete, sender=Comment)
# def comment_deleted(sender, instance: Comment, **kwargs):
#     """
#     When a comment is deleted:
#     - Invalidate the related post cache
#     """
#     invalidate_post_cache.delay(instance.post.slug)



# In your signals.py file
 # Add CustomUser if needed

# ... other receivers for Post model ...

# @receiver(m2m_changed, sender=Post.likes.through)
# def post_likes_changed(sender, instance, action, **kwargs):
#     """
#     When a user likes or unlikes a post:
#     - Invalidate the cache for the main list and the post detail.
#     - Trigger tasks to re-warm both caches with the new like_count.
#     """
#     # We only care when a like is added or removed.
#     if action in {"post_add", "post_remove"}:
#         # 'instance' here is the Post that was liked/unliked.
#         slug = instance.slug
        
#         # Invalidate first to remove stale data
#         invalidate_post_cache.delay(slug)
        
#         # Then, re-warm the caches with fresh data in the background
#         warm_posts_list_cache.delay()
#         warm_post_detail_cache.delay(slug)

from django.db import transaction
@receiver(m2m_changed, sender=Post.likes.through)
def post_likes_changed(sender, instance, action, **kwargs):
    """
    When a user likes or unlikes a post:
    - Invalidate the cache for the main list and the post detail.
    - Trigger tasks to re-warm both caches with the new like_count.
    """
    if action in {"post_add", "post_remove"}:
        slug = instance.slug

        def on_commit_tasks():
            """Tasks to run after the DB transaction is successful."""
            # Invalidate first to remove stale data immediately
            invalidate_post_cache.delay(slug)
            
            # Then, re-warm the caches with fresh data in the background
            warm_posts_list_cache.delay()
            warm_post_detail_cache.delay(slug)

        # This is the key! The function above will only be called
        # after the like/unlike is successfully committed to the database.
        transaction.on_commit(on_commit_tasks)

# In your signals.py file

# @receiver(post_save, sender=Comment)
# def comment_saved(sender, instance, created, **kwargs):
#     """
#     When a new comment is created:
#     - Invalidate the cache for the main list and the parent post.
#     - Trigger tasks to re-warm both caches with the new comment_count.
#     """
#     # We only care about newly created comments.
#     if created:
#         # 'instance' here is the Comment. We need its parent post's slug.
#         slug = instance.post.slug
        
#         # Invalidate and re-warm
#         invalidate_post_cache.delay(slug)
#         warm_posts_list_cache.delay()
#         warm_post_detail_cache.delay(slug)

# @receiver(post_delete, sender=Comment)
# def comment_deleted(sender, instance, **kwargs):
#     """
#     When a comment is deleted:
#     - Invalidate the cache for the main list and the parent post.
#     - Trigger tasks to re-warm both caches with the new comment_count.
#     """
#     slug = instance.post.slug
    
#     # Invalidate and re-warm
#     invalidate_post_cache.delay(slug)
#     warm_posts_list_cache.delay()
#     warm_post_detail_cache.delay(slug)



@receiver(post_save, sender=Comment)
def comment_saved(sender, instance, created, **kwargs):
    """
    On new comment creation, update the post's cache after the
    transaction has been committed.
    """
    if created:
        def on_commit_tasks():
            slug = instance.post.slug
            invalidate_post_cache.delay(slug)
            warm_posts_list_cache.delay()
            warm_post_detail_cache.delay(slug)

        transaction.on_commit(on_commit_tasks)

@receiver(post_delete, sender=Comment)
def comment_deleted(sender, instance, **kwargs):
    """
    On comment deletion, update the post's cache after the
    transaction has been committed.
    """
    def on_commit_tasks():
        slug = instance.post.slug
        invalidate_post_cache.delay(slug)
        warm_posts_list_cache.delay()
        warm_post_detail_cache.delay(slug)

    transaction.on_commit(on_commit_tasks)