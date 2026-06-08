from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import PendingRegistration, Transaction, User, WithdrawalRequest


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
        ("Обучение", {"fields": ("onboarding_completed_steps", "onboarding_completed_at")}),
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


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = [
        "short_public_id",
        "user",
        "amount",
        "method",
        "status",
        "bank_name",
        "card_masked",
        "created_at",
        "processed_at",
    ]
    list_filter = ["status", "method", "created_at", "processed_at"]
    search_fields = [
        "public_id",
        "user__username",
        "user__email",
        "full_name",
        "phone",
        "bank_name",
        "card_number",
    ]
    readonly_fields = [
        "public_id",
        "user",
        "amount",
        "method",
        "status",
        "full_name",
        "phone",
        "bank_name",
        "card_number",
        "card_holder",
        "reserved_transaction",
        "refund_transaction",
        "processed_by",
        "processed_at",
        "created_at",
        "updated_at",
    ]
    actions = ["mark_processing", "mark_succeeded", "reject_and_refund"]

    fieldsets = (
        ("Заявка", {
            "fields": (
                "public_id", "user", "amount", "method", "status",
                "created_at", "updated_at", "processed_at", "processed_by",
            ),
        }),
        ("Реквизиты", {
            "fields": ("full_name", "phone", "bank_name", "card_number", "card_holder"),
        }),
        ("Движение средств", {
            "fields": ("reserved_transaction", "refund_transaction"),
        }),
        ("Админская заметка", {"fields": ("admin_note",)}),
    )

    def short_public_id(self, obj):
        return str(obj.public_id)[:8]
    short_public_id.short_description = "ID"

    def mark_processing(self, request, queryset):
        changed = 0
        skipped = 0
        for withdrawal in queryset:
            ok, _message = withdrawal.mark_processing(actor=request.user)
            if ok:
                changed += 1
            else:
                skipped += 1
        if changed:
            self.message_user(request, f"Заявок взято в обработку: {changed}.", level=messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Пропущено заявок: {skipped}.", level=messages.WARNING)
    mark_processing.short_description = "Взять в обработку"

    def mark_succeeded(self, request, queryset):
        changed = 0
        skipped = 0
        for withdrawal in queryset:
            ok, _message = withdrawal.mark_succeeded(actor=request.user)
            if ok:
                changed += 1
            else:
                skipped += 1
        if changed:
            self.message_user(request, f"Заявок отмечено выплаченными: {changed}.", level=messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Пропущено заявок: {skipped}.", level=messages.WARNING)
    mark_succeeded.short_description = "Отметить выплаченными"

    def reject_and_refund(self, request, queryset):
        changed = 0
        skipped = 0
        for withdrawal in queryset:
            ok, _message = withdrawal.reject_and_refund(actor=request.user)
            if ok:
                changed += 1
            else:
                skipped += 1
        if changed:
            self.message_user(request, f"Отклонено с возвратом на баланс: {changed}.", level=messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Пропущено заявок: {skipped}.", level=messages.WARNING)
    reject_and_refund.short_description = "Отклонить и вернуть средства"
