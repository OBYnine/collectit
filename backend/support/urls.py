from django.urls import path
from . import views

urlpatterns = [
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/<int:pk>/messages/', views.ticket_message_create, name='ticket_message_create'),
    path('tickets/<int:pk>/resolve/', views.ticket_resolve_confirm, name='ticket_resolve_confirm'),
    path('admin/tickets/', views.admin_ticket_list, name='admin_ticket_list'),
    path('admin/tickets/<int:pk>/', views.admin_ticket_detail, name='admin_ticket_detail'),
]
