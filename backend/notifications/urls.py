from django.urls import path
from . import views

urlpatterns = [
    path("", views.list_notifications, name="notifications-list"),
    path("unread-count/", views.unread_count, name="notifications-unread-count"),
    path("mark-read/", views.mark_all_read, name="notifications-mark-read"),
]
