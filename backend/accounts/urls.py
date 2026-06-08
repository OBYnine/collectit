from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("verify-email/<str:token>/", views.verify_email, name="verify-email"),
    path("me/", views.me, name="me"),
    path("change-password/", views.change_password, name="change-password"),
    path("users/<str:username>/", views.user_profile, name="user-profile"),
    path("cdek-points/", views.cdek_points, name="cdek-points"),
    path("transactions/", views.transaction_list, name="transactions"),
    path("withdrawals/", views.withdrawal_requests, name="withdrawals"),
    path("deposit/", views.deposit, name="deposit"),
    path("create-payment/", views.create_payment, name="create-payment"),
    path("verify-payment/", views.verify_payment, name="verify-payment"),
    path("yookassa-webhook/", views.yookassa_webhook, name="yookassa-webhook"),
    # JWT в httpOnly cookie (вместо localStorage)
    path("cookie-login/", views.cookie_login, name="cookie-login"),
    path("cookie-refresh/", views.cookie_refresh, name="cookie-refresh"),
    path("cookie-logout/", views.cookie_logout, name="cookie-logout"),
]
