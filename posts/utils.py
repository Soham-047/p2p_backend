# posts/utils.py
from django.core.cache import cache

CACHE_POST_LIST_KEY = "posts:list"

def get_cached_posts():
    return cache.get(CACHE_POST_LIST_KEY)

def set_cached_posts(data, timeout=60):
    cache.set(CACHE_POST_LIST_KEY, data, timeout=timeout)

def clear_post_cache():
    cache.delete(CACHE_POST_LIST_KEY)
