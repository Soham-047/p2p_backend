import logging
from celery import shared_task
from django.core.cache import cache
from django.conf import settings
from .models import Post, Comment
from .cache import (
    key_posts_list, key_post_detail, key_post_comments, key_post_likes_count,
    cache_delete, cache_set, POSTS_TTL, COMMENTS_TTL
)

log = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def warm_post_detail_cache(self, slug: str):
    try:
        post = Post.objects.select_related("author").prefetch_related("tags", "likes").get(slug=slug)
        data = {
            "title": post.title,
            "content": post.content,
            "slug": post.slug,
            "tags": [t.name for t in post.tags.all()],
            "likes_count": post.likes.count(),
            "author_id": post.author_id,
        }
        cache_set(key_post_detail(slug), data, POSTS_TTL)
        return True
    except Post.DoesNotExist:
        cache_delete(key_post_detail(slug))
        return False
    except Exception as exc:
        log.exception("warm_post_detail_cache failed")
        raise self.retry(exc=exc)

@shared_task(max_retries=3, default_retry_delay=5)
def warm_posts_list_cache(self):
    try:
        payload = []
        qs = Post.objects.select_related("author").prefetch_related("tags").order_by("-created_at")[:200]
        for p in qs:
            payload.append({
                "title": p.title,
                "content": p.content,
                "slug": p.slug,
                "tags": [t.name for t in p.tags.all()],
            })
        cache_set(key_posts_list(), payload, POSTS_TTL)
        return len(payload)
    except Exception as exc:
        log.exception("warm_posts_list_cache failed")
        raise self.retry(exc=exc)

@shared_task
def invalidate_post_cache(slug: str):
    cache_delete(
        key_posts_list(),
        key_post_detail(slug),
        key_post_comments(slug),
        key_post_likes_count(slug),
    )
    return True

@shared_task
def warm_post_comments_cache(slug: str):
    try:
        post = Post.objects.get(slug=slug)
    except Post.DoesNotExist:
        cache_delete(key_post_comments(slug))
        return 0
    qs = Comment.objects.filter(post=post, parent__isnull=True).select_related("author").order_by("-created_at")
    data = [
        {
            "content": c.content,
            "slug": c.slug,
            "author_id": c.author_id,
            "created_at": c.created_at.isoformat(),
        }
        for c in qs
    ]
    cache_set(key_post_comments(slug), data, COMMENTS_TTL)
    return len(data)

@shared_task
def on_post_liked(slug: str):
    # simple invalidation (could also push notifications, webhooks, etc.)
    cache_delete(key_post_likes_count(slug), key_post_detail(slug))
    return True

@shared_task
def on_comment_created(slug: str):
    # invalidate comments and list
    cache_delete(key_post_comments(slug))
    return True
