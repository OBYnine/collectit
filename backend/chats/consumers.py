"""WebSocket consumer чата.

Заменяет HTTP polling 3 сек: фронт открывает ws://.../ws/chats/<id>/
и получает push-сообщения о новых текстах и смене статуса сделки.

Auth: scope["user"] заполняется JWTAuthMiddleware (token в query string или cookie).
Отправка из views — через broadcast_to_chat(chat_id, payload).
"""
import json

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer

from .models import Chat, Message
from .realtime import broadcast_chat_unread_count, notify_chat_message


def chat_group_name(chat_id):
    return f"chat_{chat_id}"


def broadcast_to_chat(chat_id, payload):
    """Синхронный helper: вызывается из обычных DRF views.

    Шлёт сообщение всем подключённым к группе чата. Если channel-layer не настроен
    (например, тест без Redis), просто молча пропускает.
    """
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            chat_group_name(chat_id),
            {"type": "chat.message", "payload": payload},
        )
    except Exception:
        # WebSocket — best-effort. Пуш может не дойти, polling fallback на фронте подхватит.
        pass


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Один сокет на чат. Каждый новый WS = новое соединение в группу chat_<id>."""

    async def connect(self):
        user = self.scope.get("user")
        self.chat_id = int(self.scope["url_route"]["kwargs"]["chat_id"])

        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        is_participant = await self._is_participant(self.chat_id, user.id)
        if not is_participant:
            await self.close(code=4403)
            return

        self.user_id = user.id
        self.group = chat_group_name(self.chat_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Клиент шлёт {"type": "message", "text": "..."} → создаём Message и пушим всем."""
        msg_type = content.get("type")
        if msg_type == "message":
            text = (content.get("text") or "").strip()
            if not text:
                return
            msg = await self._create_message(self.chat_id, self.user_id, text)
            payload = {
                "type": "message.created",
                "message": {
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "sender_username": msg.sender.username,
                    "text": msg.text,
                    "created_at": msg.created_at.isoformat(),
                    "is_read": False,
                },
            }
            await self.channel_layer.group_send(
                self.group,
                {"type": "chat.message", "payload": payload},
            )
        elif msg_type == "read":
            await self._mark_read(self.chat_id, self.user_id)

    # Серверный handler: вызов через group_send → доходит как event["type"] = "chat.message"
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def _is_participant(self, chat_id, user_id):
        chat = Chat.objects.filter(pk=chat_id, participants__id=user_id).first()
        if not chat:
            return False
        user_ref = type("UserRef", (), {"id": user_id, "is_authenticated": True})()
        return not chat.is_deleted_for(user_ref)

    @database_sync_to_async
    def _create_message(self, chat_id, sender_id, text):
        msg = Message.objects.create(chat_id=chat_id, sender_id=sender_id, text=text)
        # Принудительно тянем sender, чтобы не словить sync-обращение в async-коде
        msg.sender  # noqa: B018
        notify_chat_message(msg)
        return msg

    @database_sync_to_async
    def _mark_read(self, chat_id, user_id):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        if not user:
            return
        updated = (
            Message.objects
            .filter(chat_id=chat_id, is_read=False)
            .exclude(sender_id=user_id)
            .update(is_read=True)
        )
        if updated:
            broadcast_chat_unread_count(user)
