"""ASGI-точка входа для Channels.

HTTP по-прежнему отдаёт обычный Django, WebSocket уходит в URLRouter
с consumer'ами чата. Аутентификация WS — через JWT-токен в query string
(`?token=...`) или из httpOnly cookie (для одного домена).
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "collectit.settings")
django.setup()

from django.core.asgi import get_asgi_application  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

import chats.routing  # noqa: E402
import notifications.routing  # noqa: E402
from accounts.ws_auth import JWTAuthMiddlewareStack  # noqa: E402

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(
            URLRouter(
                chats.routing.websocket_urlpatterns
                + notifications.routing.websocket_urlpatterns
            )
        )
    ),
})
