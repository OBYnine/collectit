import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_notification_email(user, title, body):
    if not getattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", True):
        return False
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        return False
    try:
        send_mail(
            subject=f"CollectIT: {title}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.warning("Notification email failed for user %s: %s", user.pk, exc)
        return False
