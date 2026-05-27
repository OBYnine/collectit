from django.contrib import admin
from .models import Collection, Item, ItemImage, WishlistItem


class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 1


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "is_public", "created_at"]
    list_filter = ["is_public"]
    search_fields = ["name", "owner__username"]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "collection", "price", "is_for_sale", "created_at"]
    list_filter = ["is_for_sale"]
    search_fields = ["name", "description", "owner__username", "owner__email"]
    inlines = [ItemImageInline]


@admin.register(ItemImage)
class ItemImageAdmin(admin.ModelAdmin):
    list_display = ["id", "item", "order", "created_at"]
    search_fields = ["item__name", "item__owner__username"]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ["user", "item", "created_at"]
    search_fields = ["user__username", "user__email", "item__name"]
