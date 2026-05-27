import logging

from django.db.models import Q

from notifications.consumers import broadcast_to_user
from notifications.email import send_notification_email
from notifications.models import Notification

from .models import Message

logger = logging.getLogger(__name__)


def _notification_payload(notification):
    return {
        "id": notification.id,
        "title": notification.title,
        "body": notification.body,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }


def _message_payload(message):
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_username": message.sender.username,
        "text": message.text,
        "created_at": message.created_at.isoformat(),
        "is_read": message.is_read,
    }


def notify_user(user, title, body, event_extra=None):
    notification = Notification.objects.create(user=user, title=title, body=body)
    send_notification_email(user, title, body)
    try:
        payload = {
            "type": "notification.created",
            "notification": _notification_payload(notification),
        }
        if event_extra:
            payload.update(event_extra)
        broadcast_to_user(user.pk, payload)
    except Exception as exc:
        logger.warning("Notification realtime failed for user %s: %s", user.pk, exc)
    return notification


def chat_unread_count(user):
    return (
        Message.objects
        .filter(chat__participants=user, is_read=False)
        .exclude(sender=user)
        .exclude(chat__seller_id=user.id, chat__seller_deleted_at__isnull=False)
        .exclude(~Q(chat__seller_id=user.id), chat__buyer_deleted_at__isnull=False)
        .count()
    )


def broadcast_chat_unread_count(user):
    try:
        broadcast_to_user(user.pk, {
            "type": "chat.unread_count",
            "count": chat_unread_count(user),
        })
    except Exception as exc:
        logger.warning("Chat unread realtime failed for user %s: %s", user.pk, exc)


def notify_chat_message(message):
    message = (
        Message.objects
        .select_related("sender", "chat")
        .prefetch_related("chat__participants")
        .get(pk=message.pk)
    )
    chat = message.chat
    subject = chat.subject or "сделке"

    for recipient in chat.participants.exclude(pk=message.sender_id):
        if chat.is_deleted_for(recipient):
            continue
        unread_count = chat_unread_count(recipient)
        notify_user(
            recipient,
            "Новое сообщение",
            f"{message.sender.username} написал по {subject}.",
            event_extra={
                "kind": "chat.message",
                "chat_id": chat.pk,
                "chat_unread_count": unread_count,
            },
        )
        try:
            broadcast_to_user(recipient.pk, {
                "type": "chat.message.created",
                "chat_id": chat.pk,
                "unread_count": unread_count,
                "message": _message_payload(message),
            })
        except Exception as exc:
            logger.warning("Chat message realtime failed for user %s: %s", recipient.pk, exc)
