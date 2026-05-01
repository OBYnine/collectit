from django.contrib import admin
from .models import Collection, Item


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "is_public", "created_at"]
    list_filter = ["is_public"]
    search_fields = ["name", "owner__username"]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "price", "is_for_sale"]
    list_filter = ["is_for_sale"]
    search_fields = ["name", "description"]
