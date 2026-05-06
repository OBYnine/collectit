from django.contrib import admin
from .models import SupportMessage, SupportTicket


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ['sender', 'is_admin', 'text', 'created_at']
    fields = ['sender', 'is_admin', 'text', 'created_at']
    can_delete = False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'topic', 'status', 'created_at']
    list_filter   = ['status', 'topic']
    search_fields = ['user__username', 'user__email', 'message', 'messages__text']
    readonly_fields = ['user', 'topic', 'message', 'created_at']
    fields        = ['user', 'topic', 'message', 'status', 'admin_reply', 'created_at']
    inlines       = [SupportMessageInline]
