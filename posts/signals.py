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



