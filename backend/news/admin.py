from django.contrib import admin
from .models import Article, ArticleImage


class ArticleImageInline(admin.TabularInline):
    model = ArticleImage
    extra = 0


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title", "author", "source_site", "is_ai_generated",
        "is_published", "published_at", "views_count",
    ]
    list_filter = ["is_published", "is_ai_generated", "source_site"]
    search_fields = ["title", "content", "source_url", "source_external_id"]
    readonly_fields = [
        "source_site", "source_url", "source_external_id",
        "source_published_at", "imported_at", "ai_model", "is_ai_generated",
    ]
    inlines = [ArticleImageInline]
