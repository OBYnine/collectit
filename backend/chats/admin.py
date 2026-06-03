from django.contrib import admin
from django.contrib import messages
from django.db.models import CharField, Sum
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Chat, Deal, Message


def _extract_chat_id(search_term):
    value = (search_term or "").strip()
    upper = value.upper()
    if upper.startswith("CHAT-"):
        value = value[5:]
    elif value.startswith("#"):
        value = value[1:]
    value = value.strip()
    return int(value) if value.isdigit() else None


def _extract_deal_id_fragment(search_term):
    value = (search_term or "").strip()
    if value.upper().startswith("DEAL-"):
        value = value[5:]
    return value.strip()


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender", "text", "created_at", "is_read"]
    fields = ["sender", "text", "created_at", "is_read"]
    can_delete = False


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = [
        "id", "support_code", "subject", "seller", "price", "status", "track_number", "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["subject", "seller__username", "seller__email", "track_number", "cdek_uuid"]
    readonly_fields = [
        "participants_key", "created_at", "track_number", "cdek_uuid", "shipped_at",
    ]
    inlines = [MessageInline]

    @admin.display(description="Код")
    def support_code(self, obj):
        return f"CHAT-{obj.pk}"

    def get_search_results(self, request, queryset, search_term):
        base_queryset = queryset
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        chat_id = _extract_chat_id(search_term)
        if chat_id is not None:
            queryset = base_queryset.filter(pk=chat_id) | queryset
        return queryset, may_have_duplicates


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    change_list_template = "admin/chats/deal/change_list.html"
    list_display = [
        "short_public_id",
        "chat_link",
        "subject",
        "buyer",
        "seller",
        "amount",
        "service_fee_amount",
        "buyer_amount",
        "held_amount",
        "escrow_status",
        "status",
        "release_button",
        "refund_button",
        "created_at",
    ]
    list_filter = ["status", "escrow_status", "created_at", "paid_at", "released_at"]
    search_fields = [
        "subject",
        "buyer__username",
        "buyer__email",
        "seller__username",
        "seller__email",
    ]
    readonly_fields = [
        "public_id",
        "chat",
        "buyer",
        "seller",
        "item",
        "subject",
        "item_image",
        "amount",
        "service_fee_amount",
        "buyer_amount",
        "currency",
        "status",
        "escrow_status",
        "held_amount",
        "paid_at",
        "released_at",
        "refunded_at",
        "released_by",
        "refunded_by",
        "created_at",
        "updated_at",
    ]
    actions = ["release_held_funds_to_seller", "refund_held_funds_to_buyer"]

    def changelist_view(self, request, extra_context=None):
        total_held = Deal.objects.filter(
            escrow_status=Deal.ESCROW_HELD,
        ).aggregate(total=Sum("held_amount"))["total"] or 0
        extra_context = extra_context or {}
        extra_context["total_held_amount"] = total_held
        return super().changelist_view(request, extra_context=extra_context)

    def get_search_results(self, request, queryset, search_term):
        base_queryset = queryset
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        chat_id = _extract_chat_id(search_term)
        if chat_id is not None:
            queryset = base_queryset.filter(chat_id=chat_id) | queryset
        deal_fragment = _extract_deal_id_fragment(search_term)
        if deal_fragment:
            public_id_matches = (
                base_queryset
                .annotate(public_id_text=Cast("public_id", CharField()))
                .filter(public_id_text__icontains=deal_fragment)
            )
            queryset = public_id_matches | queryset
        return queryset, may_have_duplicates

    fieldsets = (
        ("Сделка", {
            "fields": (
                "public_id", "chat", "status", "buyer", "seller", "item",
                "subject", "item_image", "created_at", "updated_at",
            ),
        }),
        ("Деньги", {
            "fields": (
                "amount", "service_fee_amount", "buyer_amount", "currency", "escrow_status", "held_amount",
                "paid_at", "released_at", "refunded_at", "released_by", "refunded_by",
            ),
        }),
        ("Админская заметка", {"fields": ("admin_note",)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:deal_id>/release-to-seller/",
                self.admin_site.admin_view(self.release_to_seller_view),
                name="chats_deal_release_to_seller",
            ),
            path(
                "<int:deal_id>/refund-to-buyer/",
                self.admin_site.admin_view(self.refund_to_buyer_view),
                name="chats_deal_refund_to_buyer",
            ),
        ]
        return custom + urls

    @admin.display(description="ID сделки")
    def short_public_id(self, obj):
        return str(obj.public_id)[:8]

    @admin.display(description="Чат")
    def chat_link(self, obj):
        url = reverse("admin:chats_chat_change", args=[obj.chat_id])
        return format_html('<a href="{}">#{}</a>', url, obj.chat_id)

    @admin.display(description="Действие")
    def release_button(self, obj):
        if not obj.can_release_to_seller():
            return "—"
        url = reverse("admin:chats_deal_release_to_seller", args=[obj.pk])
        return format_html('<a class="button" href="{}">Зачислить продавцу</a>', url)

    @admin.display(description="Возврат")
    def refund_button(self, obj):
        if not obj.can_refund_to_buyer():
            return "—"
        url = reverse("admin:chats_deal_refund_to_buyer", args=[obj.pk])
        return format_html('<a class="button" href="{}">Вернуть покупателю</a>', url)

    @admin.action(description="Зачислить удержанные средства продавцу")
    def release_held_funds_to_seller(self, request, queryset):
        released = 0
        skipped = 0
        for deal in queryset.select_related("seller", "chat"):
            ok, message = deal.release_to_seller(
                actor=request.user,
                reason="Админское зачисление удержанных средств",
            )
            if ok:
                released += 1
            else:
                skipped += 1
                self.message_user(request, f"{deal.public_id}: {message}", level=messages.WARNING)
        if released:
            self.message_user(request, f"Зачислено продавцу по сделкам: {released}.", level=messages.SUCCESS)
        if skipped and not released:
            self.message_user(request, "Нет сделок с удержанными средствами для зачисления.", level=messages.WARNING)

    @admin.action(description="Вернуть удержанные средства покупателю")
    def refund_held_funds_to_buyer(self, request, queryset):
        refunded = 0
        skipped = 0
        for deal in queryset.select_related("buyer", "chat"):
            ok, message = deal.refund_to_buyer(
                actor=request.user,
                reason="Админский возврат удержанных средств",
            )
            if ok:
                refunded += 1
            else:
                skipped += 1
                self.message_user(request, f"{deal.public_id}: {message}", level=messages.WARNING)
        if refunded:
            self.message_user(request, f"Возвращено покупателям по сделкам: {refunded}.", level=messages.SUCCESS)
        if skipped and not refunded:
            self.message_user(request, "Нет сделок с удержанными средствами для возврата.", level=messages.WARNING)

    def release_to_seller_view(self, request, deal_id):
        deal = get_object_or_404(Deal.objects.select_related("buyer", "seller", "chat"), pk=deal_id)
        opts = self.model._meta

        if request.method == "POST":
            ok, message = deal.release_to_seller(
                actor=request.user,
                reason="Админское зачисление удержанных средств",
            )
            self.message_user(
                request,
                message,
                level=messages.SUCCESS if ok else messages.WARNING,
            )
            return redirect(reverse("admin:chats_deal_change", args=[deal.pk]))

        context = {
            **self.admin_site.each_context(request),
            "title": "Зачислить удержанные средства продавцу",
            "opts": opts,
            "deal": deal,
            "has_change_permission": self.has_change_permission(request, deal),
        }
        return TemplateResponse(
            request,
            "admin/chats/deal/release_to_seller.html",
            context,
        )

    def refund_to_buyer_view(self, request, deal_id):
        deal = get_object_or_404(Deal.objects.select_related("buyer", "seller", "chat"), pk=deal_id)
        opts = self.model._meta

        if request.method == "POST":
            ok, message = deal.refund_to_buyer(
                actor=request.user,
                reason="Админский возврат удержанных средств",
            )
            self.message_user(
                request,
                message,
                level=messages.SUCCESS if ok else messages.WARNING,
            )
            return redirect(reverse("admin:chats_deal_change", args=[deal.pk]))

        context = {
            **self.admin_site.each_context(request),
            "title": "Вернуть удержанные средства покупателю",
            "opts": opts,
            "deal": deal,
            "has_change_permission": self.has_change_permission(request, deal),
        }
        return TemplateResponse(
            request,
            "admin/chats/deal/refund_to_buyer.html",
            context,
        )
