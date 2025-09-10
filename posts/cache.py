from django.core.cache import cache
from django.conf import settings

POSTS_TTL = getattr(settings, "POSTS_CACHE_TTL", 86400)
COMMENTS_TTL = getattr(settings, "COMMENTS_CACHE_TTL", 180)

# Cache keys
def key_posts_list() -> str:
    return "posts:list:v1"

def key_post_detail(slug: str) -> str:
    return f"posts:detail:v1:{slug}"

def key_post_comments(slug: str) -> str:
    return f"posts:comments:v1:{slug}"

def key_post_likes_count(slug: str) -> str:
    return f"posts:likes_count:v1:{slug}"

# Get/Set helpers
def cache_get(key: str):
    return cache.get(key)

# def cache_set(key: str, value, ttl: int):
#     cache.set(key, value, ttl)
# The 3rd parameter is now named 'timeout'
def cache_set(key: str, value, timeout):
    # The value 300 from POSTS_TTL is correctly assigned to the 'timeout' parameter
    cache.set(key, value, timeout=timeout)
def cache_delete(*keys: str):
    for k in keys:
        cache.delete(k)

def invalidate_post(slug: str):
    cache_delete(
        key_posts_list(),
        key_post_detail(slug),
        key_post_comments(slug),
        key_post_likes_count(slug),
    )
