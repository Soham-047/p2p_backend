from django.contrib import admin
from django.db import models
from .models import (
    Post,
    Comment,
    Tag,
)

admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Tag)
