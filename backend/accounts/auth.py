"""Аутентификация по JWT, спрятанному в httpOnly-cookie.

В отличие от localStorage, эту куку нельзя прочитать JS — защита от XSS.
Frontend больше не работает с токеном напрямую: он отправляется браузером
автоматически при каждом fetch с `credentials: 'include'`.
"""
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Читает access-токен из cookie вместо Authorization-заголовка."""

    def authenticate(self, request):
        # Header-based auth по-прежнему работает (для обратной совместимости и тестов).
        header_result = super().authenticate(request)
        if header_result is not None:
            return header_result

        raw_token = request.COOKIES.get(settings.JWT_COOKIE_NAME)
        if not raw_token:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
        except Exception:
            return None
        return self.get_user(validated_token), validated_token
