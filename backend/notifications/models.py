from django.db import models
from django.conf import settings


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "notifications"
        indexes = [
            # Самый частый запрос: список непрочитанных уведомлений пользователя.
            models.Index(fields=["user", "is_read", "-created_at"],
                         name="notif_user_read_idx"),
        ]
