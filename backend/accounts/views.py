import logging
from decimal import Decimal

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction as db_transaction
from django.db.models import F
import requests as http_requests
from .serializers import UserProfileSerializer, RegisterSerializer
from .models import PendingRegistration, Transaction

logger = logging.getLogger(__name__)
User = get_user_model()


class PaymentThrottle(UserRateThrottle):
    """Отдельный throttle для платёжных endpoints (10/час)."""
    scope = "payment"


class RegisterThrottle(AnonRateThrottle):
    """Ограничивает частую отправку писем подтверждения."""
    scope = "register"


class LoginThrottle(AnonRateThrottle):
    """Ограничивает подбор паролей на login endpoints."""
    scope = "login"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginThrottle]


def _setup_yookassa():
    """Настраивает модуль yookassa один раз на запрос. Возвращает True/False."""
    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        return False
    from yookassa import Configuration
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    return True


def _credit_user(user_id, amount, description, payment_yookassa_id=None):
    """Атомарное зачисление средств + запись в Transaction с защитой от дублей.

    Возвращает True если зачислено, False если уже было зачисление по этому payment_id.
    """
    with db_transaction.atomic():
        if payment_yookassa_id and Transaction.objects.filter(
            payment_yookassa_id=payment_yookassa_id
        ).exists():
            return False
        User.objects.filter(pk=user_id).update(balance=F("balance") + amount)
        Transaction.objects.create(
            user_id=user_id,
            kind=Transaction.DEPOSIT,
            amount=amount,
            description=description,
            payment_yookassa_id=payment_yookassa_id or "",
        )
    return True


def _send_verification_email(pending_registration):
    confirm_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/verify-email/"
        f"{pending_registration.token}"
    )
    subject = "Подтверждение почты CollectIT"
    message = (
        f"Здравствуйте, {pending_registration.username}!\n\n"
        "Чтобы завершить регистрацию в CollectIT, подтвердите почту по ссылке:\n"
        f"{confirm_url}\n\n"
        f"Ссылка действует {settings.EMAIL_VERIFICATION_EXPIRE_HOURS} часов.\n"
        "Если вы не регистрировались в CollectIT, просто игнорируйте это письмо."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[pending_registration.email],
        fail_silently=False,
    )


class RegisterView(generics.CreateAPIView):
    """POST /api/accounts/register/ — создаёт заявку и отправляет письмо подтверждения."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterThrottle]

    def perform_create(self, serializer):
        pending_registration = serializer.save()
        _send_verification_email(pending_registration)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                "detail": "Письмо с подтверждением отправлено на email.",
                "email": serializer.validated_data["email"],
            },
            status=status.HTTP_202_ACCEPTED,
        )


@api_view(["GET"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def verify_email(request, token):
    """GET /api/accounts/verify-email/<token>/ — подтверждает email и создаёт пользователя."""
    try:
        pending_registration = PendingRegistration.objects.get(token=token)
    except PendingRegistration.DoesNotExist:
        return Response(
            {"detail": "Ссылка подтверждения недействительна."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if pending_registration.is_expired():
        pending_registration.delete()
        return Response(
            {"detail": "Срок действия ссылки истёк. Зарегистрируйтесь ещё раз."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with db_transaction.atomic():
        if User.objects.filter(email__iexact=pending_registration.email).exists():
            pending_registration.delete()
            return Response(
                {"detail": "Пользователь с таким email уже существует."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username__iexact=pending_registration.username).exists():
            pending_registration.delete()
            return Response(
                {"detail": "Пользователь с таким именем уже существует."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create(
            username=pending_registration.username,
            email=pending_registration.email,
            password=pending_registration.password_hash,
        )
        pending_registration.delete()

    serializer = UserProfileSerializer(user, context={"request": request})
    return Response(
        {"detail": "Email подтверждён. Аккаунт создан.", "user": serializer.data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    """GET/PATCH /api/accounts/me/ — current user profile."""
    if request.method == "GET":
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    """POST /api/accounts/change-password/"""
    user = request.user
    old_password = request.data.get("old_password", "")
    new_password = request.data.get("new_password", "")

    if not user.check_password(old_password):
        return Response({"old_password": "Неверный текущий пароль."}, status=status.HTTP_400_BAD_REQUEST)
    if len(new_password) < 8:
        return Response({"new_password": "Минимум 8 символов."}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save(update_fields=["password"])
    return Response({"detail": "Пароль изменён."})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def user_profile(request, username):
    """GET /api/accounts/users/<username>/ — public profile."""
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response({"detail": "Пользователь не найден."}, status=404)

    user.profile_views += 1
    user.save(update_fields=["profile_views"])

    serializer = UserProfileSerializer(user)
    return Response(serializer.data)


# --- CDEK proxy ---

# Демо-данные для городов (реальные адреса и координаты точек СДЭК)
_DEMO_POINTS = {
    "москва": {
        "city": {"name": "Москва", "lat": 55.7558, "lng": 37.6173},
        "points": [
            {"code": "MSK1", "name": "СДЭК Москва Центр", "address": "Москва, ул. Тверская, 12", "lat": 55.7617, "lng": 37.6068, "work_time": "Пн-Пт 9:00-20:00, Сб 10:00-18:00"},
            {"code": "MSK2", "name": "СДЭК Арбат", "address": "Москва, ул. Арбат, 35", "lat": 55.7496, "lng": 37.5970, "work_time": "Пн-Вс 9:00-21:00"},
            {"code": "MSK3", "name": "СДЭК Таганская", "address": "Москва, ул. Таганская, 40/42", "lat": 55.7403, "lng": 37.6589, "work_time": "Пн-Пт 9:00-20:00"},
            {"code": "MSK4", "name": "СДЭК Марьина Роща", "address": "Москва, ул. Сущёвский вал, 49", "lat": 55.7892, "lng": 37.5982, "work_time": "Пн-Вс 9:00-21:00"},
            {"code": "MSK5", "name": "СДЭК Хамовники", "address": "Москва, ул. Льва Толстого, 18", "lat": 55.7340, "lng": 37.5856, "work_time": "Пн-Сб 10:00-20:00"},
        ],
    },
    "санкт-петербург": {
        "city": {"name": "Санкт-Петербург", "lat": 59.9343, "lng": 30.3351},
        "points": [
            {"code": "SPB1", "name": "СДЭК Невский", "address": "Санкт-Петербург, Невский пр., 88", "lat": 59.9294, "lng": 30.3642, "work_time": "Пн-Вс 9:00-21:00"},
            {"code": "SPB2", "name": "СДЭК Васильевский остров", "address": "Санкт-Петербург, Большой пр. В.О., 55", "lat": 59.9414, "lng": 30.2835, "work_time": "Пн-Пт 9:00-20:00"},
            {"code": "SPB3", "name": "СДЭК Петроградская", "address": "Санкт-Петербург, ул. Большая Пушкарская, 10", "lat": 59.9617, "lng": 30.3138, "work_time": "Пн-Вс 10:00-20:00"},
        ],
    },
    "королев": {
        "city": {"name": "Королёв", "lat": 55.9167, "lng": 37.8500},
        "points": [
            {"code": "KOR1", "name": "СДЭК Королёв Центр", "address": "Королёв, пр. Космонавтов, 10", "lat": 55.9210, "lng": 37.8488, "work_time": "Пн-Пт 9:00-20:00, Сб 10:00-17:00"},
            {"code": "KOR2", "name": "СДЭК Королёв Мыс", "address": "Королёв, ул. Советская, 46", "lat": 55.9125, "lng": 37.8390, "work_time": "Пн-Вс 9:00-21:00"},
            {"code": "KOR3", "name": "СДЭК Королёв Болшево", "address": "Королёв, ул. Горького, 8", "lat": 55.9050, "lng": 37.8620, "work_time": "Пн-Сб 10:00-19:00"},
        ],
    },
    "екатеринбург": {
        "city": {"name": "Екатеринбург", "lat": 56.8389, "lng": 60.6057},
        "points": [
            {"code": "EKB1", "name": "СДЭК Ленина", "address": "Екатеринбург, пр. Ленина, 25", "lat": 56.8400, "lng": 60.6080, "work_time": "Пн-Вс 9:00-21:00"},
            {"code": "EKB2", "name": "СДЭК Уралмаш", "address": "Екатеринбург, пр. Космонавтов, 50", "lat": 56.8734, "lng": 60.6012, "work_time": "Пн-Пт 9:00-20:00"},
        ],
    },
    "новосибирск": {
        "city": {"name": "Новосибирск", "lat": 54.9885, "lng": 82.9207},
        "points": [
            {"code": "NSK1", "name": "СДЭК Центр", "address": "Новосибирск, ул. Ленина, 3", "lat": 54.9906, "lng": 82.9246, "work_time": "Пн-Вс 9:00-21:00"},
            {"code": "NSK2", "name": "СДЭК Академгородок", "address": "Новосибирск, пр. Академика Лаврентьева, 6", "lat": 54.8472, "lng": 83.0923, "work_time": "Пн-Пт 9:00-19:00"},
        ],
    },
    "мытищи": {
        "city": {"name": "Мытищи", "lat": 55.9116, "lng": 37.7306},
        "points": [
            {"code": "MYT1", "name": "СДЭК Мытищи Центр", "address": "Мытищи, ул. Мира, 24", "lat": 55.9150, "lng": 37.7290, "work_time": "Пн-Пт 9:00-20:00, Сб 10:00-18:00"},
            {"code": "MYT2", "name": "СДЭК Мытищи Юбилейный", "address": "Мытищи, Олимпийский пр., 15", "lat": 55.9075, "lng": 37.7412, "work_time": "Пн-Вс 9:00-21:00"},
            {"code": "MYT3", "name": "СДЭК Мытищи ТЦ Красный Кит", "address": "Мытищи, Шараповский проезд, 2", "lat": 55.9200, "lng": 37.7180, "work_time": "Пн-Вс 10:00-21:00"},
            {"code": "MYT4", "name": "СДЭК Мытищи Перловская", "address": "Мытищи, ул. Летная, 40", "lat": 55.9020, "lng": 37.7520, "work_time": "Пн-Сб 9:00-20:00"},
        ],
    },
}


def _get_cdek_token():
    token = cache.get("cdek_token")
    if not token:
        client_id = settings.CDEK_CLIENT_ID
        client_secret = settings.CDEK_CLIENT_SECRET
        if not client_id or not client_secret:
            raise ValueError("CDEK credentials not configured")
        res = http_requests.post(
            f"{settings.CDEK_BASE_URL}/oauth/token?parameters",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        token = data["access_token"]
        cache.set("cdek_token", token, timeout=data.get("expires_in", 3600) - 60)
    return token


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def cdek_points(request):
    """GET /api/accounts/cdek-points/?city=Москва — city is optional.
    Without city: returns points from real API (or all demo points as fallback).
    With city: returns city center + points from real API (or demo fallback)."""
    import logging
    logger = logging.getLogger(__name__)

    city_name = request.query_params.get("city", "").strip()

    # Пробуем реальный API если настроен
    if settings.CDEK_CLIENT_ID and settings.CDEK_CLIENT_SECRET:
        try:
            token = _get_cdek_token()
            headers = {"Authorization": f"Bearer {token}"}

            if not city_name:
                # Без города — берём точки по всей России (первые 100)
                pts_res = http_requests.get(
                    f"{settings.CDEK_BASE_URL}/deliverypoints",
                    headers=headers,
                    params={"country_code": "RU", "type": "PVZ", "size": 100},
                    timeout=10,
                )
                pts_res.raise_for_status()
                raw = pts_res.json() or []
                points = []
                for p in raw:
                    loc = p.get("location", {})
                    lat, lng = loc.get("latitude"), loc.get("longitude")
                    if lat and lng:
                        points.append({
                            "code": p["code"],
                            "name": p.get("name", ""),
                            "address": loc.get("address_full") or loc.get("address", ""),
                            "lat": lat, "lng": lng,
                            "work_time": p.get("work_time", ""),
                        })
                logger.info(f"CDEK real API: got {len(points)} points (no city filter)")
                return Response({"points": points})

            else:
                # С городом — ищем город, затем его точки
                city_res = http_requests.get(
                    f"{settings.CDEK_BASE_URL}/location/cities",
                    headers=headers,
                    params={"country_codes[0]": "RU", "city": city_name, "size": 5},
                    timeout=10,
                )
                city_res.raise_for_status()
                cities = city_res.json()
                if cities:
                    city = cities[0]
                    pts_res = http_requests.get(
                        f"{settings.CDEK_BASE_URL}/deliverypoints",
                        headers=headers,
                        params={"country_code": "RU", "city_code": city["code"], "type": "PVZ", "size": 150},
                        timeout=10,
                    )
                    pts_res.raise_for_status()
                    raw = pts_res.json() or []
                    points = []
                    for p in raw:
                        loc = p.get("location", {})
                        lat, lng = loc.get("latitude"), loc.get("longitude")
                        if lat and lng:
                            points.append({
                                "code": p["code"],
                                "name": p.get("name", ""),
                                "address": loc.get("address_full") or loc.get("address", ""),
                                "lat": lat, "lng": lng,
                                "work_time": p.get("work_time", ""),
                            })
                    logger.info(f"CDEK real API: got {len(points)} points for city '{city_name}'")
                    return Response({
                        "city": {"name": city.get("city", city_name), "lat": city.get("latitude"), "lng": city.get("longitude")},
                        "points": points,
                    })
        except Exception as e:
            logger.error(f"CDEK API error (city='{city_name}'): {type(e).__name__}: {e}")
            # Fallback to demo data

    # Демо-данные
    if not city_name:
        all_points = []
        for entry in _DEMO_POINTS.values():
            all_points.extend(entry["points"])
        return Response({"points": all_points})

    key = city_name.lower()
    demo = _DEMO_POINTS.get(key)
    if demo:
        return Response(demo)

    # Неизвестный город — возвращаем Москву со сменой названия
    fallback = dict(_DEMO_POINTS["москва"])
    fallback["city"] = dict(fallback["city"])
    fallback["city"]["name"] = city_name
    fallback["_demo"] = True
    return Response(fallback)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([PaymentThrottle])
def create_payment(request):
    """POST /api/accounts/create-payment/ — создать платёж через ЮKassa."""
    from yookassa import Payment as YooPayment
    import uuid

    try:
        amount = round(float(request.data.get("amount", 0)), 2)
    except (TypeError, ValueError):
        return Response({"detail": "Некорректная сумма."}, status=status.HTTP_400_BAD_REQUEST)
    if amount <= 0 or amount > 100_000:
        return Response(
            {"detail": "Сумма должна быть от 0.01 до 100 000 ₽."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _setup_yookassa():
        return Response({"detail": "ЮKassa не настроена."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        payment = YooPayment.create({
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": f"{settings.FRONTEND_URL}/balance",
            },
            "capture": True,
            "description": f"Пополнение баланса CollectIT на {amount:.2f} ₽",
            "metadata": {"user_id": request.user.id},
        }, str(uuid.uuid4()))
    except Exception as e:
        logger.error("YooKassa create_payment error: %s", e)
        return Response({"detail": f"Ошибка ЮKassa: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

    logger.info("Payment created: user_id=%s amount=%s payment_id=%s",
                request.user.id, amount, payment.id)
    return Response({
        "payment_id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url,
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([PaymentThrottle])
def verify_payment(request):
    """POST /api/accounts/verify-payment/ — проверить статус и зачислить баланс.

    Идемпотентно: повторный вызов с тем же payment_id не зачислит дважды.
    """
    from yookassa import Payment as YooPayment

    payment_id = request.data.get("payment_id", "").strip()
    if not payment_id:
        return Response({"detail": "payment_id обязателен."}, status=status.HTTP_400_BAD_REQUEST)

    if Transaction.objects.filter(payment_yookassa_id=payment_id).exists():
        request.user.refresh_from_db(fields=["balance"])
        return Response({"status": "already_credited", "balance": str(request.user.balance)})

    if not _setup_yookassa():
        return Response({"detail": "ЮKassa не настроена."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        payment = YooPayment.find_one(payment_id)
    except Exception as e:
        logger.error("YooKassa find_one error (payment=%s): %s", payment_id, e)
        return Response({"detail": f"Ошибка ЮKassa: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

    if payment.status != "succeeded":
        return Response({"status": payment.status})

    amount = Decimal(str(payment.amount.value))
    credited = _credit_user(
        user_id=request.user.id,
        amount=amount,
        description="Пополнение через ЮKassa",
        payment_yookassa_id=payment_id,
    )
    request.user.refresh_from_db(fields=["balance"])
    logger.info(
        "Payment verified: user_id=%s amount=%s payment_id=%s credited=%s",
        request.user.id, amount, payment_id, credited,
    )
    return Response({
        "status": "succeeded" if credited else "already_credited",
        "balance": str(request.user.balance),
    })


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def transaction_list(request):
    """GET /api/accounts/transactions/ — история операций текущего пользователя."""
    txs = Transaction.objects.filter(user=request.user).values(
        "id", "kind", "amount", "description", "created_at"
    )
    return Response(list(txs))


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([PaymentThrottle])
def deposit(request):
    """POST /api/accounts/deposit/ — пополнить баланс (демо/тест)."""
    if not (settings.ENABLE_DEMO_DEPOSIT or request.user.is_staff):
        return Response(
            {"detail": "Демо-пополнение отключено."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        amount = round(float(request.data.get("amount", 0)), 2)
    except (TypeError, ValueError):
        return Response({"detail": "Некорректная сумма."}, status=status.HTTP_400_BAD_REQUEST)
    if amount <= 0 or amount > 100_000:
        return Response(
            {"detail": "Сумма должна быть от 0.01 до 100 000 ₽."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    _credit_user(
        user_id=request.user.id,
        amount=Decimal(str(amount)),
        description="Пополнение баланса",
    )
    request.user.refresh_from_db(fields=["balance"])
    return Response({"balance": str(request.user.balance)}, status=status.HTTP_200_OK)


# --- YooKassa webhook ---

# Официальные подсети ЮKassa, с которых приходят webhook'и.
# Источник: https://yookassa.ru/developers/using-api/webhooks
_YOOKASSA_ALLOWED_NETWORKS = [
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.154.128/25",
    "77.75.156.11/32",
    "77.75.156.35/32",
    "2a02:5180::/32",
]


def _client_ip(request):
    """Берём IP клиента из доверенного nginx-заголовка или REMOTE_ADDR."""
    real_ip = request.META.get("HTTP_X_REAL_IP", "").strip()
    if real_ip:
        return real_ip
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _ip_allowed_yookassa(ip):
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in _YOOKASSA_ALLOWED_NETWORKS:
        try:
            if addr in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    # В DEBUG разрешаем локалхост для тестов через curl
    if settings.DEBUG and ip in ("127.0.0.1", "::1", "localhost"):
        return True
    return False


# --- JWT cookie auth ---

def _set_jwt_cookies(response, access, refresh):
    """Кладёт access/refresh в httpOnly cookie. Параметры взяты из settings."""
    from datetime import timedelta as _td
    common = {
        "secure": settings.JWT_COOKIE_SECURE,
        "samesite": settings.JWT_COOKIE_SAMESITE,
        "httponly": True,
        "domain": settings.JWT_COOKIE_DOMAIN,
        "path": "/",
    }
    # Совпадает с SIMPLE_JWT lifetimes (1ч / 7д). Для access ставим max_age = 1ч,
    # для refresh = 7д. SameSite=Lax + httpOnly закроют XSS+CSRF в браузере.
    access_lifetime = settings.SIMPLE_JWT.get("ACCESS_TOKEN_LIFETIME", _td(hours=1))
    refresh_lifetime = settings.SIMPLE_JWT.get("REFRESH_TOKEN_LIFETIME", _td(days=7))

    response.set_cookie(
        settings.JWT_COOKIE_NAME, access,
        max_age=int(access_lifetime.total_seconds()),
        **common,
    )
    if refresh:
        response.set_cookie(
            settings.JWT_REFRESH_COOKIE_NAME, refresh,
            max_age=int(refresh_lifetime.total_seconds()),
            **common,
        )
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@throttle_classes([LoginThrottle])
def cookie_login(request):
    """POST /api/accounts/cookie-login/ — выдаёт JWT в httpOnly cookie.

    Тело: {"email": "...", "password": "..."}.
    Возвращает {"user": {...}} (токенов в теле нет — они в cookie).
    """
    from django.contrib.auth import authenticate
    from rest_framework_simplejwt.tokens import RefreshToken

    email = (request.data.get("email") or "").strip()
    password = request.data.get("password") or ""
    if not email or not password:
        return Response({"detail": "email/password обязательны."},
                        status=status.HTTP_400_BAD_REQUEST)
    user = authenticate(request, email=email, password=password)
    if not user:
        return Response({"detail": "Неверный email или пароль."},
                        status=status.HTTP_401_UNAUTHORIZED)

    refresh = RefreshToken.for_user(user)
    serializer = UserProfileSerializer(user, context={"request": request})
    response = Response({"user": serializer.data})
    _set_jwt_cookies(response, str(refresh.access_token), str(refresh))
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def cookie_refresh(request):
    """POST /api/accounts/cookie-refresh/ — обновляет access по refresh cookie.

    Тело пустое; refresh-токен берётся из httpOnly cookie.
    """
    from rest_framework_simplejwt.tokens import RefreshToken
    from rest_framework_simplejwt.exceptions import TokenError

    raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
    if not raw_refresh:
        return Response({"detail": "no refresh cookie"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        refresh = RefreshToken(raw_refresh)
    except TokenError:
        return Response({"detail": "invalid refresh"}, status=status.HTTP_401_UNAUTHORIZED)

    response = Response({"ok": True})
    _set_jwt_cookies(response, str(refresh.access_token), None)
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def cookie_logout(request):
    """POST /api/accounts/cookie-logout/ — стирает JWT cookies."""
    response = Response({"ok": True})
    response.delete_cookie(settings.JWT_COOKIE_NAME, path="/", domain=settings.JWT_COOKIE_DOMAIN)
    response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME, path="/", domain=settings.JWT_COOKIE_DOMAIN)
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def yookassa_webhook(request):
    """POST /api/accounts/yookassa-webhook/ — уведомления от ЮKassa.

    Проверяем IP источника по белому списку подсетей ЮKassa. Для события
    payment.succeeded достаём payment_id из payload, подтверждаем через
    YooKassa API и зачисляем средства (идемпотентно).
    """
    from yookassa import Payment as YooPayment

    ip = _client_ip(request)
    if not _ip_allowed_yookassa(ip):
        logger.warning("YooKassa webhook rejected — untrusted IP: %s", ip)
        return Response({"detail": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

    event = request.data.get("event")
    obj = request.data.get("object") or {}
    payment_id = obj.get("id", "")
    logger.info("YooKassa webhook: event=%s payment_id=%s ip=%s", event, payment_id, ip)

    if event != "payment.succeeded" or not payment_id:
        # Остальные события (waiting_for_capture, canceled и т.д.) просто подтверждаем.
        return Response({"ok": True})

    if not _setup_yookassa():
        logger.error("YooKassa webhook: credentials not set")
        return Response({"detail": "not configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Подтверждаем платеж через API — не доверяем данным из webhook напрямую.
    try:
        payment = YooPayment.find_one(payment_id)
    except Exception as e:
        logger.error("YooKassa webhook find_one failed: %s", e)
        return Response({"detail": "yookassa error"}, status=status.HTTP_502_BAD_GATEWAY)

    if payment.status != "succeeded":
        return Response({"ok": True, "status": payment.status})

    metadata = payment.metadata or {}
    user_id = metadata.get("user_id")
    if not user_id:
        logger.error("YooKassa webhook: user_id missing in metadata, payment=%s", payment_id)
        return Response({"detail": "no user_id in metadata"}, status=status.HTTP_400_BAD_REQUEST)

    amount = Decimal(str(payment.amount.value))
    credited = _credit_user(
        user_id=int(user_id),
        amount=amount,
        description="Пополнение через ЮKassa (webhook)",
        payment_yookassa_id=payment_id,
    )
    logger.info(
        "Webhook credit: user_id=%s amount=%s payment_id=%s credited=%s",
        user_id, amount, payment_id, credited,
    )
    return Response({"ok": True, "credited": credited})
