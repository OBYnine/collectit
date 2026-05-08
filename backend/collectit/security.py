from urllib.parse import urlparse

from django.conf import settings
from django.http import JsonResponse


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class ApiOriginProtectionMiddleware:
    """Reject cross-site unsafe browser requests to the API.

    JWT lives in httpOnly cookies, so SameSite=Lax is the first CSRF barrier.
    This middleware adds an Origin check for POST/PATCH/PUT/DELETE requests.
    Non-browser integrations such as YooKassa webhooks usually do not send
    Origin and continue to work.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/") and request.method not in SAFE_METHODS:
            origin = request.META.get("HTTP_ORIGIN")
            if origin and origin not in self._allowed_origins(request):
                return JsonResponse({"detail": "Cross-origin request rejected."}, status=403)
        return self.get_response(request)

    def _allowed_origins(self, request):
        allowed = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
        frontend_url = getattr(settings, "FRONTEND_URL", "")
        if frontend_url:
            allowed.add(self._origin(frontend_url))
        allowed.add(f"{request.scheme}://{request.get_host()}")
        return {origin for origin in allowed if origin}

    @staticmethod
    def _origin(url):
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}"
