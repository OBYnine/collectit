import json

from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from .models import Article, ArticleImage
from .serializers import ArticleListSerializer, ArticleDetailSerializer


class IsNewsEditor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_news_editor or request.user.is_staff
        )


class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.filter(is_published=True).select_related("author").prefetch_related("images")
    search_fields = ["title", "excerpt", "content"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsNewsEditor()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ArticleDetailSerializer
        return ArticleListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.views_count += 1
        instance.save(update_fields=["views_count"])
        return super().retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user and not request.user.is_staff:
            return Response({"detail": "Нет прав для удаления."}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):
        title   = request.data.get("title", "").strip()
        content = request.data.get("content", "").strip()
        if not title or not content:
            return Response({"detail": "Заголовок и текст обязательны."}, status=status.HTTP_400_BAD_REQUEST)

        excerpt = content[:300] + ("…" if len(content) > 300 else "")
        article = Article.objects.create(
            title=title,
            content=content,
            excerpt=excerpt,
            author=request.user,
            is_published=True,
            published_at=timezone.now(),
        )

        for i, img in enumerate(request.FILES.getlist("images")):
            ArticleImage.objects.create(article=article, image=img, order=i)

        return Response(ArticleListSerializer(article).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user and not request.user.is_staff:
            return Response({"detail": "Нет прав для редактирования."}, status=status.HTTP_403_FORBIDDEN)

        title   = request.data.get("title", "").strip()
        content = request.data.get("content", "").strip()
        if not title or not content:
            return Response({"detail": "Заголовок и текст обязательны."}, status=status.HTTP_400_BAD_REQUEST)

        instance.title   = title
        instance.content = content
        instance.excerpt = content[:300] + ("…" if len(content) > 300 else "")
        instance.save()

        # Удаляем отмеченные изображения
        raw = request.data.get("remove_image_ids", "[]")
        try:
            remove_ids = json.loads(raw)
        except (ValueError, TypeError):
            remove_ids = []
        if remove_ids:
            ArticleImage.objects.filter(article=instance, id__in=remove_ids).delete()

        # Добавляем новые изображения
        existing_count = instance.images.count()
        for i, img in enumerate(request.FILES.getlist("images")):
            ArticleImage.objects.create(article=instance, image=img, order=existing_count + i)

        instance.refresh_from_db()
        return Response(ArticleListSerializer(instance).data)
