from django.db import models
from django.conf import settings


class ArticleImage(models.Model):
    article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='images')
    image   = models.ImageField(upload_to='news/images/')
    order   = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "article_images"
        ordering = ['order']


class Article(models.Model):
    title = models.CharField(max_length=300)
    excerpt = models.TextField(max_length=500)
    content = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views_count = models.PositiveIntegerField(default=0)
    source_site = models.CharField(max_length=120, blank=True)
    source_url = models.URLField(max_length=1000, blank=True, null=True)
    source_external_id = models.CharField(max_length=120, blank=True, db_index=True)
    source_published_at = models.DateTimeField(null=True, blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    ai_model = models.CharField(max_length=120, blank=True)
    is_ai_generated = models.BooleanField(default=False)

    class Meta:
        db_table = "articles"
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        ordering = ["-published_at"]

    def __str__(self):
        return self.title
