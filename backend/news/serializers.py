from rest_framework import serializers
from .models import Article, ArticleImage


class ArticleImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleImage
        fields = ["id", "image"]


class ArticleListSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    images      = ArticleImageSerializer(many=True, read_only=True)

    def get_author_name(self, obj):
        if obj.author_id and obj.author:
            return obj.author.username
        if obj.is_ai_generated:
            return obj.ai_model or "AI"
        return ""

    class Meta:
        model = Article
        fields = [
            "id", "title", "excerpt", "content",
            "author_name", "published_at", "views_count", "images",
            "source_site", "source_url", "is_ai_generated",
        ]


class ArticleDetailSerializer(ArticleListSerializer):
    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields
