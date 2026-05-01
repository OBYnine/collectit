from django.db import models
from django.conf import settings


class Collection(models.Model):
    """A user's named collection of items."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="collections"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_emoji = models.CharField(max_length=10, default="📦")
    color = models.CharField(max_length=7, default="#3b82f6")  # hex
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "collections"
        verbose_name = "Коллекция"
        verbose_name_plural = "Коллекции"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    @property
    def items_count(self):
        return self.items.count()


class Item(models.Model):
    """A single collectible item."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, null=True, blank=True, related_name="items"
    )

    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    is_for_sale = models.BooleanField(default=False)

    image = models.ImageField(upload_to="items/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "items"
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class WishlistItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist"
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="wishlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "wishlist"
        unique_together = ("user", "item")
