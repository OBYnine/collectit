from django.contrib import admin
from .models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'topic', 'status', 'created_at']
    list_filter   = ['status', 'topic']
    search_fields = ['user__username', 'message']
    readonly_fields = ['user', 'topic', 'message', 'created_at']
    fields        = ['user', 'topic', 'message', 'status', 'admin_reply', 'created_at']
