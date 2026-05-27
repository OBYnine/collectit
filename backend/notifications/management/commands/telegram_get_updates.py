import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Print recent Telegram chats that interacted with the configured bot."

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not configured.")

        try:
            response = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                timeout=settings.TELEGRAM_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise CommandError(f"Telegram getUpdates failed: {exc}") from exc

        if not data.get("ok"):
            raise CommandError(f"Telegram returned error: {data}")

        chats = {}
        for update in data.get("result", []):
            message = update.get("message") or update.get("edited_message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is None:
                continue
            chats[str(chat_id)] = {
                "id": chat_id,
                "type": chat.get("type", ""),
                "title": chat.get("title") or chat.get("username") or "",
                "first_name": chat.get("first_name") or "",
                "last_name": chat.get("last_name") or "",
            }

        if not chats:
            self.stdout.write(
                "No chats found. Send /start to the bot from the admin Telegram account, then run this command again."
            )
            return

        for chat in chats.values():
            name = " ".join(
                value for value in (chat["title"], chat["first_name"], chat["last_name"]) if value
            )
            self.stdout.write(f"{chat['id']}\t{chat['type']}\t{name}".rstrip())
