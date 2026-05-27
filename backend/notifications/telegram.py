import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LENGTH = 3900


def send_telegram_message(text):
    if not getattr(settings, "TELEGRAM_NOTIFICATIONS_ENABLED", True):
        return False

    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_ids = getattr(settings, "TELEGRAM_ADMIN_CHAT_IDS", [])
    if not token or not chat_ids:
        logger.info("Telegram notifications are not configured")
        return False

    ok = True
    url = TELEGRAM_API_BASE.format(token=token, method="sendMessage")
    for chat_id in chat_ids:
        try:
            response = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": _truncate_message(text),
                    "disable_web_page_preview": True,
                },
                timeout=getattr(settings, "TELEGRAM_REQUEST_TIMEOUT", 10),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            ok = False
            logger.warning("Telegram notification failed for chat %s: %s", chat_id, exc)
    return ok


def send_support_ticket_telegram(ticket, *, event="new", message_text=None):
    event_title = {
        "new": "Новое обращение в поддержку",
        "reply": "Пользователь дополнил обращение",
    }.get(event, "Обращение в поддержку")
    user = ticket.user
    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    admin_tickets_url = f"{frontend_url}/admin/tickets" if frontend_url else ""
    django_admin_url = (
        f"{frontend_url}/admin/support/supportticket/{ticket.pk}/change/"
        if frontend_url
        else ""
    )

    parts = [
        f"CollectIT: {event_title}",
        f"Тикет: #{ticket.pk}",
        f"Тема: {ticket.get_topic_display_ru()}",
        f"Пользователь: {user.username} ({user.email or 'email не указан'})",
        "",
        "Сообщение:",
        _truncate_message(message_text if message_text is not None else ticket.message, max_length=1200),
    ]
    if admin_tickets_url:
        parts.extend(["", f"Админка тикетов: {admin_tickets_url}"])
    if django_admin_url:
        parts.append(f"Django Admin: {django_admin_url}")

    return send_telegram_message("\n".join(parts))


def _truncate_message(text, max_length=MAX_MESSAGE_LENGTH):
    text = str(text or "").strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"
