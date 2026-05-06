"""User-level realtime events.

One websocket per browser session subscribes to notifications for the current
user. Staff users also join a staff-wide group so admin screens can receive
support-ticket updates immediately.
"""
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer


def user_group_name(user_id):
    return f"user_notifications_{user_id}"


def staff_group_name():
    return "staff_notifications"


def broadcast_to_user(user_id, payload):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            user_group_name(user_id),
            {"type": "user.event", "payload": payload},
        )
    except Exception:
        pass


def broadcast_to_staff(payload):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            staff_group_name(),
            {"type": "user.event", "payload": payload},
        )
    except Exception:
        pass


class UserEventsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user_group = user_group_name(user.id)
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        self.staff_group = None
        if user.is_staff:
            self.staff_group = staff_group_name()
            await self.channel_layer.group_add(self.staff_group, self.channel_name)

        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        if getattr(self, "staff_group", None):
            await self.channel_layer.group_discard(self.staff_group, self.channel_name)

    async def user_event(self, event):
        await self.send_json(event["payload"])
