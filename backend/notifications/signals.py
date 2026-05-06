from django.db.models.signals import post_save
from django.dispatch import receiver

from .consumers import broadcast_to_user
from .models import Notification
from .serializers import NotificationSerializer


@receiver(post_save, sender=Notification)
def push_notification_created(sender, instance, created, **kwargs):
    if not created:
        return
    broadcast_to_user(instance.user_id, {
        "type": "notification.created",
        "notification": NotificationSerializer(instance).data,
    })
