from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

import logging
import re

from collectit.pricing import buyer_amount, service_fee_amount

from .models import Chat, Deal, Message
from .realtime import broadcast_chat_unread_count, chat_unread_count, notify_chat_message, notify_user
from .serializers import ChatSerializer, MessageSerializer

logger = logging.getLogger(__name__)

User = get_user_model()


class ChatMessageThrottle(UserRateThrottle):
    scope = "chat_message"

    def allow_request(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return super().allow_request(request, view)


def _cdek_phone(user):
    raw = (getattr(user, "phone", "") or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = f"7{digits}"
    elif len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"
    if len(digits) < 10:
        return ""
    return f"+{digits}"


def _has_phone(user):
    return bool(_cdek_phone(user))


def _create_cdek_order(chat, buyer, seller):
    """Создаёт заказ в СДЭК API. Возвращает (cdek_uuid, cdek_number).
    Выбрасывает исключение если что-то пошло не так."""
    from django.conf import settings
    import time
    import requests as http_requests
    from accounts.views import _get_cdek_token

    token = _get_cdek_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if not _has_phone(seller) or not _has_phone(buyer):
        raise ValueError("Для создания заказа СДЭК у продавца и покупателя должны быть заполнены телефоны.")

    payload = {
        "tariff_code": 136,  # ПВЗ → ПВЗ
        "shipment_point": seller.delivery_point_code,
        "delivery_point": buyer.delivery_point_code,
        "sender": {
            "name": seller.username,
            "phones": [{"number": _cdek_phone(seller)}],
        },
        "recipient": {
            "name": buyer.username,
            "phones": [{"number": _cdek_phone(buyer)}],
        },
        "packages": [{
            "number": "1",
            "weight": 500,
            "length": 20,
            "width": 20,
            "height": 20,
            "items": [{
                "name": chat.subject or "Предмет коллекции",
                "ware_key": f"item_{chat.pk}",
                "payment": {"value": 0},
                "cost": float(chat.price or 0),
                "weight": 500,
                "amount": 1,
            }],
        }],
    }

    res = http_requests.post(
        f"{settings.CDEK_BASE_URL}/orders",
        json=payload,
        headers=headers,
        timeout=15,
    )
    res.raise_for_status()
    data = res.json()

    cdek_uuid = data.get("entity", {}).get("uuid")
    if not cdek_uuid:
        raise ValueError(f"СДЭК не вернул UUID заказа: {data}")

    # Небольшая пауза — СДЭК иногда не отдаёт cdek_number сразу
    time.sleep(1)
    detail_res = http_requests.get(
        f"{settings.CDEK_BASE_URL}/orders/{cdek_uuid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    detail_res.raise_for_status()
    detail = detail_res.json()
    cdek_number = detail.get("entity", {}).get("cdek_number") or cdek_uuid[:12]

    logger.info(f"CDEK order created: uuid={cdek_uuid}, number={cdek_number}")
    return cdek_uuid, cdek_number


def _notify(user, title, body):
    notify_user(user, title, body)


def _ws_chat_updated(chat, request=None):
    """Шлёт всем участникам чата актуальный объект Chat по WebSocket."""
    try:
        from .consumers import broadcast_to_chat
        ctx = {"request": request} if request else {}
        broadcast_to_chat(chat.pk, {
            "type": "chat.updated",
            "chat": ChatSerializer(chat, context=ctx).data,
        })
    except Exception as exc:
        logger.warning("WS broadcast failed for chat %s: %s", chat.pk, exc)


def _check_and_arrive(chat):
    """Если посылка отправлена > 60 сек назад — переводим статус в arrived.

    ВАЖНО: деньги продавцу здесь НЕ зачисляются! Эскроу удерживает их до тех пор,
    пока покупатель не нажмёт «Подтвердить получение» (chat_confirm_receipt).
    Это защищает покупателя от пропавших посылок.

    Защищено от гонки: select_for_update блокирует чат, double-check статуса
    внутри транзакции не даст сменить статус дважды.
    """
    if not chat.maybe_arrive():
        return chat

    arrived_now = False
    with db_transaction.atomic():
        locked = Chat.objects.select_for_update().get(pk=chat.pk)
        if locked.status != Chat.STATUS_SHIPPED:
            # Кто-то уже успел сменить статус — выходим.
            return locked
        locked.status = Chat.STATUS_ARRIVED
        locked.save(update_fields=["status"])
        Deal.sync_from_chat(locked)
        chat = locked
        arrived_now = True

    if arrived_now:
        buyer = chat.participants.exclude(pk=chat.seller_id).first()
        if buyer:
            _notify(buyer, "Посылка прибыла — заберите и подтвердите",
                    f"Посылка «{chat.subject or 'предмет'}» прибыла в пункт выдачи. "
                    f"Заберите её и нажмите «Я получил товар» в чате — после этого "
                    f"{chat.price} ₽ будут переведены продавцу.")
        # Продавец увидит статус «прибыла», но деньги — после подтверждения покупателя.
        if chat.seller_id:
            seller = User.objects.filter(pk=chat.seller_id).first()
            if seller:
                _notify(seller, "Посылка доставлена в ПВЗ покупателя",
                        f"Посылка «{chat.subject or 'предмет'}» доставлена. "
                        f"Ожидаем подтверждения получения от покупателя — после этого "
                        f"{chat.price} ₽ будут зачислены вам.")
        _ws_chat_updated(chat)

    return chat


def _exclude_deleted_for_user(queryset, user):
    return (
        queryset
        .exclude(seller_id=user.id, seller_deleted_at__isnull=False)
        .exclude(~Q(seller_id=user.id), buyer_deleted_at__isnull=False)
    )


def _sync_sale_quotes(chats):
    synced = list(chats)
    for chat in synced:
        chat.sync_price_from_item()
    return synced


def _is_archived_for(chat, user):
    """Чат перешёл в архив (Сделки) для данного пользователя."""
    if chat.seller_id == user.id:
        return chat.status == Chat.STATUS_COMPLETED and not chat.is_deleted_for(user)
    return chat.status == Chat.STATUS_COMPLETED and not chat.is_deleted_for(user)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def deals_list(request):
    """GET /api/chats/deals/ — завершённые сделки текущего пользователя (архив)."""
    all_chats = (
        _exclude_deleted_for_user(
            Chat.objects.filter(participants=request.user, status=Chat.STATUS_COMPLETED),
            request.user,
        )
        .prefetch_related("participants", "messages")
        .order_by("-created_at")
    )
    archived = [c for c in all_chats if _is_archived_for(c, request.user)]
    return Response(ChatSerializer(archived, many=True, context={"request": request}).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def chat_list(request):
    if request.method == "GET":
        all_chats = (
            _exclude_deleted_for_user(
                Chat.objects.filter(participants=request.user).exclude(status=Chat.STATUS_COMPLETED),
                request.user,
            )
            .select_related("item", "item__owner", "seller")
            .prefetch_related("participants", "messages")
            .order_by("-created_at")
        )
        all_chats = _sync_sale_quotes(all_chats)
        # Исключаем чаты, которые пользователь уже отправил в архив
        return Response(ChatSerializer(all_chats, many=True, context={"request": request}).data)

    username = request.data.get("username", "").strip()
    if not username:
        return Response({"detail": "username required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        other = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    if other == request.user:
        return Response({"detail": "Cannot chat with yourself"}, status=status.HTTP_400_BAD_REQUEST)

    subject    = request.data.get("item_name", "").strip()
    item_image = request.data.get("item_image", "").strip()
    seller     = other if request.data.get("seller_is_other") else None

    price = None
    raw_price = request.data.get("item_price")
    if raw_price is not None:
        try:
            price = Decimal(str(raw_price))
        except InvalidOperation:
            pass

    item = None
    item_id = request.data.get("item_id")
    if item_id:
        from collectibles.models import Item
        item = Item.objects.select_related("owner").filter(pk=item_id).first()
        if not item:
            return Response({"detail": "Item not found"}, status=status.HTTP_404_NOT_FOUND)
        if item.owner_id != other.id:
            return Response(
                {"detail": "Предмет не принадлежит продавцу."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not item.is_for_sale:
            return Response(
                {"detail": "Предмет не выставлен на продажу."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        seller = item.owner
        price = item.price

    chat, created = Chat.get_or_create_between(
        request.user, other,
        subject=subject, item_image=item_image,
        seller=seller, price=price, item=item,
    )
    return Response(
        ChatSerializer(chat, context={"request": request}).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count(request):
    return Response({"count": chat_unread_count(request.user)})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ChatMessageThrottle])
def message_list(request, chat_id):
    try:
        chat = (
            Chat.objects
            .select_related("item", "item__owner", "seller")
            .filter(participants=request.user)
            .get(pk=chat_id)
        )
    except Chat.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    if chat.is_deleted_for(request.user):
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    # Проверяем авто-прибытие при каждом опросе
    chat = _check_and_arrive(chat)
    chat.sync_price_from_item()

    if request.method == "GET":
        read_count = chat.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
        if read_count:
            broadcast_chat_unread_count(request.user)
        messages = chat.messages.select_related("sender").all()
        return Response({
            "messages": MessageSerializer(messages, many=True, context={"request": request}).data,
            "chat": ChatSerializer(chat, context={"request": request}).data,
        })

    text = request.data.get("text", "").strip()
    if not text:
        return Response({"detail": "text required"}, status=status.HTTP_400_BAD_REQUEST)
    msg = Message.objects.create(chat=chat, sender=request.user, text=text)

    # Если кто-то слушает чат по WebSocket — push обновление.
    try:
        from .consumers import broadcast_to_chat
        broadcast_to_chat(chat.pk, {
            "type": "message.created",
            "message": {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "sender_username": request.user.username,
                "text": msg.text,
                "created_at": msg.created_at.isoformat(),
                "is_read": False,
            },
        })
    except Exception as exc:
        logger.warning("WS broadcast failed for chat %s: %s", chat.pk, exc)
    notify_chat_message(msg)

    return Response(MessageSerializer(msg, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE", "POST"])
@permission_classes([IsAuthenticated])
def hide_chat(request, chat_id):
    try:
        chat = Chat.objects.filter(participants=request.user).get(pk=chat_id)
    except Chat.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    chat.mark_deleted_for(request.user)
    broadcast_chat_unread_count(request.user)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_agree(request, chat_id):
    """Продавец соглашается на сделку → уведомляет покупателя."""
    try:
        chat = (
            Chat.objects
            .select_related("item", "item__owner", "seller")
            .filter(participants=request.user, seller=request.user)
            .get(pk=chat_id)
        )
    except Chat.DoesNotExist:
        return Response({"detail": "Not found or you are not the seller"}, status=status.HTTP_404_NOT_FOUND)

    if chat.status != Chat.STATUS_PENDING:
        return Response({"detail": "Already agreed"}, status=status.HTTP_400_BAD_REQUEST)
    if not _has_phone(request.user):
        return Response(
            {"detail": "Укажите номер телефона в настройках профиля перед согласием на сделку. Он нужен для оформления доставки СДЭК."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Синхронизируем цену с актуальной ценой предмета
    chat.sync_price_from_item()
    chat.status = Chat.STATUS_AGREED
    chat.save(update_fields=["status"])
    Deal.sync_from_chat(chat)

    buyer = chat.participants.exclude(pk=request.user.pk).first()
    if buyer:
        _notify(buyer, "Продавец согласен на сделку",
                f"{request.user.username} согласился продать «{chat.subject or 'предмет'}» за {chat.price} ₽. Можно оплатить в чате.")

    _ws_chat_updated(chat, request)
    return Response(ChatSerializer(chat, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_pay(request, chat_id):
    """Покупатель оплачивает — деньги удерживаются на сайте (эскроу). Уведомляет продавца с адресом ПВЗ.

    Защита от гонки: списание баланса через атомарный UPDATE с фильтром
    balance >= price (если параллельно два pay-запроса, второй вернёт 400).
    """
    from accounts.models import Transaction

    try:
        chat = (
            Chat.objects
            .select_related("seller", "item", "item__owner")
            .filter(participants=request.user)
            .get(pk=chat_id)
        )
    except Chat.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if chat.seller_id == request.user.id:
        return Response({"detail": "Seller cannot pay"}, status=status.HTTP_400_BAD_REQUEST)
    if chat.status != Chat.STATUS_AGREED:
        return Response({"detail": "Seller has not agreed yet"}, status=status.HTTP_400_BAD_REQUEST)
    chat.sync_price_from_item()
    if chat.price is None:
        return Response({"detail": "No price set"}, status=status.HTTP_400_BAD_REQUEST)

    buyer = request.user
    seller = chat.seller
    buyer_total = buyer_amount(chat.price)

    if not _has_phone(buyer):
        return Response(
            {"detail": "Укажите номер телефона в настройках профиля перед оплатой. Он нужен для оформления доставки СДЭК."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not seller:
        return Response(
            {"detail": "Продавец не найден для этой сделки."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not _has_phone(seller):
        return Response(
            {"detail": "Продавец не указал номер телефона. Попросите его заполнить телефон в настройках профиля перед сделкой."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Предварительная проверка (даёт лучший UX-ответ) — но не гарантирует атомарность, её даст UPDATE ниже.
    if buyer.balance < buyer_total:
        return Response(
            {"detail": f"Недостаточно средств. Баланс: {buyer.balance} ₽, нужно: {buyer_total} ₽."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not buyer.delivery_point_code:
        return Response(
            {"detail": "Укажите пункт выдачи СДЭК в настройках профиля перед оплатой."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not seller.delivery_point_code:
        return Response(
            {"detail": "Продавец не указал свой пункт выдачи СДЭК. Попросите его заполнить настройки доставки."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Создаём заказ СДЭК до списания денег — если API упадёт, деньги не уйдут
    try:
        cdek_uuid, cdek_number = _create_cdek_order(chat, buyer, seller)
    except Exception as e:
        logger.error(f"CDEK order failed for chat {chat_id}: {type(e).__name__}: {e}")
        return Response(
            {"detail": f"Не удалось создать заказ СДЭК: {e}. Попробуйте позже."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    with db_transaction.atomic():
        # Блокируем чат — защита от параллельных pay по одному и тому же чату.
        locked_chat = Chat.objects.select_for_update().get(pk=chat.pk)
        if locked_chat.status != Chat.STATUS_AGREED:
            return Response({"detail": "Оплата уже произведена."}, status=status.HTTP_400_BAD_REQUEST)

        # Атомарное списание: update срабатывает только если баланс >= price.
        locked_chat.sync_price_from_item()
        if locked_chat.price is None:
            return Response({"detail": "No price set"}, status=status.HTTP_400_BAD_REQUEST)
        locked_fee_amount = service_fee_amount(locked_chat.price)
        locked_buyer_total = buyer_amount(locked_chat.price)
        affected = User.objects.filter(pk=buyer.pk, balance__gte=locked_buyer_total).update(
            balance=F("balance") - locked_buyer_total
        )
        if not affected:
            return Response(
                {"detail": "Недостаточно средств (списание отклонено)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Transaction.objects.create(
            user=buyer,
            kind=Transaction.EXPENSE,
            amount=locked_buyer_total,
            description=f"Оплата (эскроу): {locked_chat.subject or 'предмет'}",
        )
        locked_chat.status = Chat.STATUS_PAID
        locked_chat.cdek_uuid = cdek_uuid
        locked_chat.track_number = cdek_number
        locked_chat.save(update_fields=["status", "cdek_uuid", "track_number"])
        deal = Deal.ensure_for_chat(
            locked_chat,
            buyer=buyer,
            seller=locked_chat.seller,
            item=locked_chat.item,
            amount=locked_chat.price,
        )
        if deal:
            deal.mark_held(
                locked_chat.price,
                buyer_total=locked_buyer_total,
                service_fee=locked_fee_amount,
            )
        chat = locked_chat

    # Обновляем объект buyer, чтобы вернуть актуальный баланс
    buyer.refresh_from_db(fields=["balance"])

    seller_pvz = seller.delivery_point_address or seller.delivery_city
    _notify(seller, "Покупатель оплатил — сдайте посылку в СДЭК",
            f"{buyer.username} оплатил «{chat.subject or 'предмет'}» ({chat.price} ₽). "
            f"Заказ СДЭК № {cdek_number} создан. "
            f"Сдайте посылку в ваш ПВЗ: {seller_pvz}. "
            f"После сдачи нажмите «Я сдал в СДЭК» в чате.")

    _ws_chat_updated(chat, request)
    return Response({
        **ChatSerializer(chat, context={"request": request}).data,
        "new_balance": str(buyer.balance),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_ship(request, chat_id):
    """Продавец отправил посылку: генерирует трек-номер, удаляет предмет, уведомляет покупателя."""
    try:
        chat = Chat.objects.select_related("seller", "item").filter(
            participants=request.user, seller=request.user
        ).get(pk=chat_id)
    except Chat.DoesNotExist:
        return Response({"detail": "Not found or you are not the seller"}, status=status.HTTP_404_NOT_FOUND)

    if chat.status != Chat.STATUS_PAID:
        return Response({"detail": "Payment not received yet"}, status=status.HTTP_400_BAD_REQUEST)

    chat.shipped_at = timezone.now()
    chat.status     = Chat.STATUS_SHIPPED
    update_fields   = ["shipped_at", "status", "item"]

    # Удаляем предмет из коллекции продавца. Если удалить не удалось —
    # логируем и всё равно отвязываем от чата, чтобы не блокировать отправку.
    if chat.item_id:
        try:
            chat.item.delete()
        except Exception as e:
            logger.exception(
                "Failed to delete item %s for chat %s: %s",
                chat.item_id, chat.pk, e,
            )
        chat.item = None

    chat.save(update_fields=update_fields)
    Deal.sync_from_chat(chat)

    # Шедулим точный таймер прибытия через Celery (60 сек). При CELERY_TASK_ALWAYS_EAGER
    # (например, в тестах без Redis) задача выполнится синхронно, поэтому подставим
    # try/except — фронт всё равно подхватит auto-arrive через polling fallback.
    try:
        from .tasks import check_and_arrive_chat
        check_and_arrive_chat.apply_async(args=[chat.pk], countdown=60)
    except Exception as exc:
        logger.warning("Failed to schedule check_and_arrive_chat for chat %s: %s",
                       chat.pk, exc)

    track = chat.track_number  # Уже записан при оплате (от СДЭК) или пустой
    buyer = chat.participants.exclude(pk=request.user.pk).first()
    if buyer:
        track_info = f"Номер заказа СДЭК: {track}." if track else "Отслеживайте статус в приложении СДЭК."
        _notify(buyer, "Посылка сдана в СДЭК",
                f"«{chat.subject or 'предмет'}» сдан в пункт выдачи! {track_info} "
                f"Ожидайте уведомления о прибытии.")

    # Push в WebSocket (если кто-то слушает чат) — обновит UI без polling.
    try:
        from .consumers import broadcast_to_chat
        broadcast_to_chat(chat.pk, {
            "type": "chat.updated",
            "chat": ChatSerializer(chat, context={"request": request}).data,
        })
    except Exception as exc:
        logger.warning("WS broadcast failed for chat %s: %s", chat.pk, exc)

    return Response(ChatSerializer(chat, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rate_chat(request, chat_id):
    """Покупатель выставляет оценку продавцу → чат уходит в архив покупателя."""
    try:
        chat = Chat.objects.select_related("seller").filter(participants=request.user).get(pk=chat_id)
    except Chat.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if chat.seller_id == request.user.id:
        return Response({"detail": "Продавец не может оценивать сам себя."}, status=status.HTTP_400_BAD_REQUEST)
    if chat.status != Chat.STATUS_COMPLETED:
        return Response({"detail": "Сделка ещё не завершена."}, status=status.HTTP_400_BAD_REQUEST)
    if chat.buyer_confirmed:
        return Response({"detail": "Оценка уже выставлена."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        rating = int(request.data.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0
    if rating not in range(1, 6):
        return Response({"detail": "Оценка должна быть от 1 до 5."}, status=status.HTTP_400_BAD_REQUEST)

    chat.rating = rating
    chat.buyer_confirmed = True
    chat.save(update_fields=["rating", "buyer_confirmed"])
    _ws_chat_updated(chat, request)

    # Пересчитываем средний рейтинг продавца
    seller = chat.seller
    if seller:
        from django.db.models import Avg
        avg = Chat.objects.filter(seller=seller, rating__isnull=False).aggregate(a=Avg("rating"))["a"]
        seller.rating = round(avg, 2) if avg else 0
        seller.save(update_fields=["rating"])
        _notify(seller, f"Новая оценка: {'★' * rating}{'☆' * (5 - rating)}",
                f"{request.user.username} оценил сделку «{chat.subject or 'предмет'}» на {rating}/5. "
                f"Подтвердите в чате, чтобы убрать его из списка.")

    return Response(ChatSerializer(chat, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def acknowledge_rating(request, chat_id):
    """Продавец подтверждает оценку → чат уходит в архив продавца."""
    try:
        chat = Chat.objects.filter(participants=request.user, seller=request.user).get(pk=chat_id)
    except Chat.DoesNotExist:
        return Response({"detail": "Not found or you are not the seller"}, status=status.HTTP_404_NOT_FOUND)

    if chat.status != Chat.STATUS_COMPLETED:
        return Response({"detail": "Сделка ещё не завершена."}, status=status.HTTP_400_BAD_REQUEST)
    if not chat.buyer_confirmed:
        return Response({"detail": "Покупатель ещё не выставил оценку."}, status=status.HTTP_400_BAD_REQUEST)
    if chat.seller_confirmed:
        return Response({"detail": "Уже подтверждено."}, status=status.HTTP_400_BAD_REQUEST)

    chat.seller_confirmed = True
    chat.save(update_fields=["seller_confirmed"])
    _ws_chat_updated(chat, request)

    return Response(ChatSerializer(chat, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_confirm_receipt(request, chat_id):
    """Покупатель подтверждает получение → деньги переводятся продавцу.

    Это и есть момент «выпуска» эскроу: до сих пор сумма висела на сайте, теперь
    идёт на баланс продавца. Защита от гонки — атомарный F()-update + select_for_update.
    """
    try:
        chat = Chat.objects.select_related("seller").filter(participants=request.user).get(pk=chat_id)
    except Chat.DoesNotExist:
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if chat.seller_id == request.user.id:
        return Response({"detail": "Seller cannot confirm receipt"}, status=status.HTTP_400_BAD_REQUEST)
    if chat.status != Chat.STATUS_ARRIVED:
        return Response({"detail": "Package has not arrived yet"}, status=status.HTTP_400_BAD_REQUEST)

    credited = False
    with db_transaction.atomic():
        # Блокируем чат — два параллельных подтверждения не зачислят дважды.
        locked = Chat.objects.select_for_update().get(pk=chat.pk)
        if locked.status != Chat.STATUS_ARRIVED:
            return Response({"detail": "Already completed."},
                            status=status.HTTP_400_BAD_REQUEST)

        locked.status = Chat.STATUS_COMPLETED
        locked.save(update_fields=["status"])
        deal = Deal.ensure_for_chat(
            locked,
            seller=locked.seller,
            item=locked.item,
            amount=locked.price,
        )
        if deal and deal.escrow_status == Deal.ESCROW_NOT_HELD and locked.price:
            deal.mark_held(
                locked.price,
                buyer_total=buyer_amount(locked.price),
                service_fee=service_fee_amount(locked.price),
            )
        if deal:
            credited, _message = deal.release_to_seller(
                reason="Продажа",
            )
        chat = locked

    if credited and chat.seller_id:
        seller = User.objects.filter(pk=chat.seller_id).first()
        if seller:
            _notify(seller, "Деньги зачислены — покупатель подтвердил получение",
                    f"{request.user.username} подтвердил получение «{chat.subject or 'предмет'}». "
                    f"{chat.price} ₽ зачислено на ваш счёт.")

    _ws_chat_updated(chat, request)
    return Response(ChatSerializer(chat, context={"request": request}).data)
