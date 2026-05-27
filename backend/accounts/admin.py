from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import PendingRegistration, Transaction, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "is_news_editor", "total_items", "total_collections"]
    list_filter = ["is_news_editor", "is_staff"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Личная информация", {"fields": ("first_name", "last_name", "email")}),
        ("Права доступа", {"fields": ("is_active", "is_staff", "is_superuser", "user_permissions")}),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
        ("Роли", {"fields": ("is_news_editor",)}),
        ("Коллекционер", {"fields": ("avatar", "bio", "phone")}),
        ("Статистика", {"fields": ("total_items", "total_collections", "total_trades", "rating", "profile_views")}),
        ("Доставка", {"fields": ("delivery_city", "delivery_point_code", "delivery_point_address")}),
    )


@admin.register(PendingRegistration)
class PendingRegistrationAdmin(admin.ModelAdmin):
    list_display = ["email", "username", "created_at", "expires_at"]
    search_fields = ["email", "username"]
    readonly_fields = ["username", "email", "password_hash", "token", "created_at", "expires_at"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "kind", "amount", "description", "payment_yookassa_id", "created_at"]
    list_filter = ["kind", "created_at"]
    search_fields = ["user__username", "user__email", "description", "payment_yookassa_id"]
    readonly_fields = ["user", "kind", "amount", "description", "payment_yookassa_id", "created_at"]
