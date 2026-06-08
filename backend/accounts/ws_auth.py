"""JWT-аутентификация для WebSocket.

Токен читается из Cookie access_token=<...>.
Legacy query string ?token=<access> отключен по умолчанию, потому что URL
часто попадает в логи reverse proxy/браузера/мониторинга.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


@database_sync_to_async
def _get_user(user_id):
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


def _extract_token(scope):
    if settings.ALLOW_WEBSOCKET_QUERY_TOKEN:
        qs = parse_qs(scope.get("query_string", b"").decode())
        if "token" in qs and qs["token"]:
            return qs["token"][0]
    # cookie fallback
    cookies = {}
    for header_name, header_value in scope.get("headers", []):
        if header_name == b"cookie":
            for part in header_value.decode().split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    cookies[k] = v
    return cookies.get(settings.JWT_COOKIE_NAME)


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        token = _extract_token(scope)
        scope["user"] = AnonymousUser()
        if token:
            try:
                access = AccessToken(token)
                scope["user"] = await _get_user(access["user_id"])
            except Exception:
                pass
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
