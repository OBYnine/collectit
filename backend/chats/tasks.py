"""Фоновые задачи для эскроу-сделок.

- check_and_arrive_chat — точный таймер прибытия (вместо HTTP polling 3с).
  Шедулится из chat_ship через apply_async(countdown=60).
- retry_create_cdek_order — повтор создания заказа СДЭК при флаповом 502/timeout.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="chats.check_and_arrive_chat", ignore_result=True)
def check_and_arrive_chat(chat_id: int):
    """Через 60 секунд после ship — переводим в arrived и зачисляем продавцу.

    Идемпотентно: если статус уже не shipped, ничего не меняет.
    """
    from .models import Chat
    from .views import _check_and_arrive

    chat = Chat.objects.filter(pk=chat_id).first()
    if not chat:
        logger.warning("check_and_arrive_chat: chat %s not found", chat_id)
        return
    _check_and_arrive(chat)
    logger.info("check_and_arrive_chat: chat %s processed", chat_id)


@shared_task(
    name="chats.retry_create_cdek_order",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def retry_create_cdek_order(self, chat_id: int):
    """Повторная попытка создать СДЭК-заказ для уже оплаченного чата (paid).

    Используется как compensation если при chat_pay СДЭК упал, а деньги уже списаны.
    Сейчас не используется автоматически — оставлено как утилита для админ-команды.
    """
    from accounts.models import User
    from .models import Chat
    from .views import _create_cdek_order

    chat = (
        Chat.objects
        .select_related("seller")
        .prefetch_related("participants")
        .filter(pk=chat_id)
        .first()
    )
    if not chat:
        logger.warning("retry_create_cdek_order: chat %s not found", chat_id)
        return
    if chat.cdek_uuid:
        logger.info("retry_create_cdek_order: chat %s already has cdek_uuid, skip", chat_id)
        return

    seller = chat.seller
    buyer = chat.participants.exclude(pk=getattr(seller, "id", None)).first()
    if not seller or not buyer:
        logger.error("retry_create_cdek_order: seller/buyer missing for chat %s", chat_id)
        return

    cdek_uuid, cdek_number = _create_cdek_order(chat, buyer, seller)
    Chat.objects.filter(pk=chat.pk).update(cdek_uuid=cdek_uuid, track_number=cdek_number)
    logger.info("retry_create_cdek_order: chat %s -> uuid=%s number=%s",
                chat_id, cdek_uuid, cdek_number)
