import logging
from decimal import Decimal

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes, authentication_classes
from rest_framework.exceptions import APIException
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
from .serializers import RegisterSerializer, UserProfileSerializer, WithdrawalRequestSerializer
from .models import PendingRegistration, Transaction, WithdrawalRequest

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


class VerificationEmailUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Не удалось отправить письмо подтверждения. Попробуйте позже."
    default_code = "verification_email_unavailable"


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


_YOOKASSA_CANCELLATION_MESSAGES = {
    "3d_secure_failed": "Не пройдена 3-D Secure проверка. Попробуйте повторить оплату или используйте другую карту.",
    "call_issuer": "Банк отклонил оплату. Обратитесь в банк или используйте другую карту.",
    "canceled_by_merchant": "Платеж отменен магазином.",
    "card_expired": "Срок действия карты истек. Используйте другую карту.",
    "country_forbidden": "Оплата картой, выпущенной в этой стране, запрещена. Используйте другое платежное средство.",
    "deal_expired": "Срок жизни сделки истек. Создайте новый платеж, если хотите продолжить оплату.",
    "expired_on_capture": "Истек срок списания оплаты. Повторите платеж.",
    "expired_on_confirmation": "Истек срок подтверждения оплаты. Создайте новый платеж и подтвердите его.",
    "fraud_suspected": "Платеж отклонен из-за подозрения в мошенничестве. Используйте другое платежное средство.",
    "general_decline": "Платеж отклонен без детальной причины. Обратитесь в банк или попробуйте другой способ оплаты.",
    "identification_required": "Для кошелька ЮMoney превышены ограничения. Пройдите идентификацию или выберите другой способ оплаты.",
    "insufficient_funds": "На платежном средстве недостаточно средств. Пополните баланс или используйте другую карту.",
    "internal_timeout": "ЮKassa не успела обработать платеж. Повторите оплату новым платежом.",
    "invalid_card_number": "Неверно указан номер карты. Проверьте данные и попробуйте снова.",
    "invalid_csc": "Неверно указан CVV/CVC-код. Проверьте данные и попробуйте снова.",
    "issuer_unavailable": "Банк сейчас недоступен. Повторите оплату позже или используйте другую карту.",
    "payment_method_limit_exceeded": "Превышен лимит платежей для карты или магазина. Используйте другой способ оплаты или повторите позже.",
    "payment_method_restricted": "Операции этим платежным средством запрещены. Обратитесь в банк или используйте другую карту.",
    "permission_revoked": "Разрешение на автоплатеж отозвано. Создайте новый платеж и подтвердите оплату.",
    "unsupported_mobile_operator": "Этот мобильный оператор не поддерживается. Используйте другое платежное средство.",
}

_YOOKASSA_CANCELLATION_PARTIES = {
    "merchant": "магазин",
    "yoo_money": "ЮKassa",
    "payment_network": "платежная система или банк",
}


def _object_value(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _payment_metadata_user_id(payment):
    metadata = _object_value(payment, "metadata", {}) or {}
    user_id = _object_value(metadata, "user_id")
    if user_id in (None, ""):
        return ""
    return str(user_id).strip()


def _payment_cancellation_payload(payment):
    details = _object_value(payment, "cancellation_details")
    party = str(_object_value(details, "party", "") or "").strip()
    reason = str(_object_value(details, "reason", "") or "").strip()
    message = _YOOKASSA_CANCELLATION_MESSAGES.get(
        reason,
        "Платеж отменен. Попробуйте повторить оплату или выберите другой способ оплаты.",
    )
    payload = {"party": party, "reason": reason, "message": message}
    if party:
        payload["party_label"] = _YOOKASSA_CANCELLATION_PARTIES.get(party, party)
    return payload


def _payment_status_payload(payment):
    payment_status = str(_object_value(payment, "status", "unknown") or "unknown")
    payload = {"status": payment_status}
    if payment_status == "canceled":
        cancellation_details = _payment_cancellation_payload(payment)
        payload["cancellation_details"] = cancellation_details
        payload["message"] = cancellation_details["message"]
    return payload


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
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterThrottle]

    def perform_create(self, serializer):
        pending_registration = serializer.save()
        try:
            _send_verification_email(pending_registration)
        except Exception:
            logger.exception(
                "Failed to send verification email for pending_registration_id=%s",
                pending_registration.id,
            )
            pending_registration.delete()
            raise VerificationEmailUnavailable()

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
            terms_accepted_at=pending_registration.terms_accepted_at,
            terms_version=pending_registration.terms_version,
            personal_data_accepted_at=pending_registration.personal_data_accepted_at,
            personal_data_version=pending_registration.personal_data_version,
            consent_ip=pending_registration.consent_ip,
            consent_user_agent=pending_registration.consent_user_agent,
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
        request.user.sync_onboarding_progress()
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    user.sync_onboarding_progress()
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

    existing_tx = Transaction.objects.filter(payment_yookassa_id=payment_id).only(
        "user_id"
    ).first()
    if existing_tx:
        if existing_tx.user_id != request.user.id:
            logger.warning(
                "YooKassa verify rejected: payment_id=%s credited_to=%s requested_by=%s",
                payment_id, existing_tx.user_id, request.user.id,
            )
            return Response(
                {"detail": "Платеж не принадлежит текущему пользователю."},
                status=status.HTTP_403_FORBIDDEN,
            )
        request.user.refresh_from_db(fields=["balance"])
        return Response({"status": "already_credited", "balance": str(request.user.balance)})

    if not _setup_yookassa():
        return Response({"detail": "ЮKassa не настроена."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        payment = YooPayment.find_one(payment_id)
    except Exception as e:
        logger.error("YooKassa find_one error (payment=%s): %s", payment_id, e)
        return Response({"detail": f"Ошибка ЮKassa: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

    payment_user_id = _payment_metadata_user_id(payment)
    if payment_user_id != str(request.user.id):
        logger.warning(
            "YooKassa verify rejected: metadata user mismatch payment=%s metadata_user=%s requested_by=%s",
            payment_id, payment_user_id or "<missing>", request.user.id,
        )
        return Response(
            {"detail": "Платеж не принадлежит текущему пользователю."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if payment.status != "succeeded":
        return Response(_payment_status_payload(payment))

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


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([PaymentThrottle])
def withdrawal_requests(request):
    """GET/POST /api/accounts/withdrawals/ — ручные заявки на вывод средств."""
    if request.method == "GET":
        queryset = WithdrawalRequest.objects.filter(user=request.user)
        return Response(WithdrawalRequestSerializer(queryset, many=True).data)

    serializer = WithdrawalRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    amount = data["amount"]
    method = data["method"]

    with db_transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=request.user.pk)
        if WithdrawalRequest.objects.filter(
            user=locked_user,
            status__in=WithdrawalRequest.ACTIVE_STATUSES,
        ).exists():
            return Response(
                {"detail": "У вас уже есть заявка на вывод в обработке."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        affected = User.objects.filter(pk=locked_user.pk, balance__gte=amount).update(
            balance=F("balance") - amount
        )
        if not affected:
            return Response(
                {"detail": "Недостаточно средств для вывода."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        method_label = dict(WithdrawalRequest.METHOD_CHOICES).get(method, method)
        reserve_tx = Transaction.objects.create(
            user=locked_user,
            kind=Transaction.EXPENSE,
            amount=amount,
            description=f"Резерв вывода средств ({method_label})",
        )
        withdrawal = WithdrawalRequest.objects.create(
            user=locked_user,
            amount=amount,
            method=method,
            full_name=data["full_name"],
            phone=data.get("phone", ""),
            bank_name=data.get("bank_name", ""),
            card_number=data.get("card_number", ""),
            card_holder=data.get("card_holder", ""),
            reserved_transaction=reserve_tx,
        )
        locked_user.refresh_from_db(fields=["balance"])

    return Response(
        {
            "withdrawal": WithdrawalRequestSerializer(withdrawal).data,
            "balance": str(locked_user.balance),
        },
        status=status.HTTP_201_CREATED,
    )


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
    # Совпадает с SIMPLE_JWT lifetimes. SameSite=Lax + httpOnly уменьшают
    # риск XSS/CSRF, а Secure на prod не даёт отправлять cookie по HTTP.
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

    user.sync_onboarding_progress()
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

    Тело пустое; refresh-токен берётся из httpOnly cookie. При включенной
    ротации SimpleJWT старый refresh попадает в blacklist, а клиент получает
    новый refresh-cookie.
    """
    from rest_framework_simplejwt.tokens import RefreshToken
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.settings import api_settings

    raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
    if not raw_refresh:
        return Response({"detail": "no refresh cookie"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        refresh = RefreshToken(raw_refresh)
    except TokenError:
        return Response({"detail": "invalid refresh"}, status=status.HTTP_401_UNAUTHORIZED)

    access_token = str(refresh.access_token)
    new_refresh = None
    if api_settings.ROTATE_REFRESH_TOKENS:
        if api_settings.BLACKLIST_AFTER_ROTATION:
            try:
                refresh.blacklist()
            except AttributeError:
                logger.warning("Refresh token blacklist app is not installed.")
            except TokenError:
                return Response({"detail": "invalid refresh"}, status=status.HTTP_401_UNAUTHORIZED)
        refresh.set_jti()
        refresh.set_exp()
        refresh.set_iat()
        new_refresh = str(refresh)

    response = Response({"ok": True})
    _set_jwt_cookies(response, access_token, new_refresh)
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def cookie_logout(request):
    """POST /api/accounts/cookie-logout/ — стирает JWT cookies."""
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import RefreshToken

    raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
    if raw_refresh:
        try:
            RefreshToken(raw_refresh).blacklist()
        except (AttributeError, TokenError):
            pass

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

    if event not in ("payment.succeeded", "payment.canceled") or not payment_id:
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

    if event == "payment.canceled" or payment.status == "canceled":
        cancellation_details = _payment_cancellation_payload(payment)
        logger.warning(
            "YooKassa payment canceled: payment_id=%s user_id=%s party=%s reason=%s",
            payment_id,
            _payment_metadata_user_id(payment) or "<missing>",
            cancellation_details.get("party") or "<missing>",
            cancellation_details.get("reason") or "<missing>",
        )
        return Response({
            "ok": True,
            "status": payment.status,
            "cancellation_details": cancellation_details,
        })

    if payment.status != "succeeded":
        return Response({"ok": True, "status": payment.status})

    user_id = _payment_metadata_user_id(payment)
    if not user_id:
        logger.error("YooKassa webhook: user_id missing in metadata, payment=%s", payment_id)
        return Response({"detail": "no user_id in metadata"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        logger.error(
            "YooKassa webhook: invalid user_id in metadata, payment=%s user_id=%s",
            payment_id, user_id,
        )
        return Response({"detail": "invalid user_id in metadata"}, status=status.HTTP_400_BAD_REQUEST)

    amount = Decimal(str(payment.amount.value))
    credited = _credit_user(
        user_id=user_id_int,
        amount=amount,
        description="Пополнение через ЮKassa (webhook)",
        payment_yookassa_id=payment_id,
    )
    logger.info(
        "Webhook credit: user_id=%s amount=%s payment_id=%s credited=%s",
        user_id, amount, payment_id, credited,
    )
    return Response({"ok": True, "credited": credited})
