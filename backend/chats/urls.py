from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_list, name="chat_list"),
    path("deals/", views.deals_list, name="deals_list"),
    path("unread-count/", views.unread_count, name="chat_unread_count"),
    path("<int:chat_id>/messages/", views.message_list, name="message_list"),
    path("<int:chat_id>/agree/", views.chat_agree, name="chat_agree"),
    path("<int:chat_id>/pay/", views.chat_pay, name="chat_pay"),
    path("<int:chat_id>/ship/", views.chat_ship, name="chat_ship"),
    path("<int:chat_id>/confirm-receipt/", views.chat_confirm_receipt, name="chat_confirm_receipt"),
    path("<int:chat_id>/rate/", views.rate_chat, name="rate_chat"),
    path("<int:chat_id>/acknowledge/", views.acknowledge_rating, name="acknowledge_rating"),
]
