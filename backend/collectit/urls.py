from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    # Apps
    path("api/accounts/", include("accounts.urls")),
    path("api/collections/", include("collectibles.urls")),
    path("api/news/", include("news.urls")),
    path("api/search/", include("search.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/chats/", include("chats.urls")),
    path("api/support/", include("support.urls")),
]

if settings.ENABLE_LEGACY_JWT_ENDPOINTS:
    from rest_framework_simplejwt.views import TokenRefreshView
    from accounts.views import ThrottledTokenObtainPairView

    urlpatterns += [
        path("api/auth/token/", ThrottledTokenObtainPairView.as_view(), name="token_obtain"),
        path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    ]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
