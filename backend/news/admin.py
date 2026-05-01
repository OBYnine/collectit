from django.contrib import admin
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "is_published", "published_at", "views_count"]
    list_filter = ["is_published"]
    search_fields = ["title", "content"]
