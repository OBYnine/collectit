from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Transaction
from collectibles.models import Collection, Item

from .models import Chat, Deal


User = get_user_model()


class SaleQuoteSyncTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com",
            username="seller",
            password="password",
        )
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            username="buyer",
            password="password",
        )
        self.collection = Collection.objects.create(
            owner=self.seller,
            name="Coins",
        )
        self.item = Item.objects.create(
            owner=self.seller,
            collection=self.collection,
            name="Test coin",
            price=Decimal("100.00"),
            is_for_sale=True,
        )
        self.chat, _ = Chat.get_or_create_between(
            self.buyer,
            self.seller,
            subject=self.item.name,
            seller=self.seller,
            price=self.item.price,
            item=self.item,
        )

    def test_item_price_change_updates_pending_chat_and_deal(self):
        self.item.price = Decimal("150.00")
        self.item.save(update_fields=["price"])

        self.chat.refresh_from_db()
        self.chat.deal.refresh_from_db()

        self.assertEqual(self.chat.price, Decimal("150.00"))
        self.assertEqual(self.chat.deal.amount, Decimal("150.00"))
        self.assertEqual(self.chat.deal.service_fee_amount, Decimal("10.50"))
        self.assertEqual(self.chat.deal.buyer_amount, Decimal("160.50"))

    def test_existing_chat_reopen_updates_mutable_deal_amount(self):
        Item.objects.filter(pk=self.item.pk).update(price=Decimal("175.00"))
        self.item.refresh_from_db()

        chat, created = Chat.get_or_create_between(
            self.buyer,
            self.seller,
            subject=self.item.name,
            seller=self.seller,
            price=self.item.price,
            item=self.item,
        )
        chat.refresh_from_db()
        chat.deal.refresh_from_db()

        self.assertFalse(created)
        self.assertEqual(chat.price, Decimal("175.00"))
        self.assertEqual(chat.deal.amount, Decimal("175.00"))
        self.assertEqual(chat.deal.service_fee_amount, Decimal("12.25"))
        self.assertEqual(chat.deal.buyer_amount, Decimal("187.25"))

    def test_item_price_clear_removes_pending_chat_price(self):
        self.item.price = None
        self.item.save(update_fields=["price"])

        self.chat.refresh_from_db()
        self.chat.deal.refresh_from_db()

        self.assertIsNone(self.chat.price)
        self.assertEqual(self.chat.deal.amount, Decimal("0.00"))
        self.assertEqual(self.chat.deal.service_fee_amount, Decimal("0.00"))
        self.assertEqual(self.chat.deal.buyer_amount, Decimal("0.00"))

    def test_held_deal_amount_is_not_changed_by_item_price(self):
        self.chat.status = Chat.STATUS_PAID
        self.chat.save(update_fields=["status"])
        deal = Deal.sync_from_chat(self.chat)
        deal.mark_held(self.chat.price)

        self.item.price = Decimal("220.00")
        self.item.save(update_fields=["price"])

        self.chat.refresh_from_db()
        deal.refresh_from_db()

        self.assertEqual(self.chat.price, Decimal("100.00"))
        self.assertEqual(deal.amount, Decimal("100.00"))
        self.assertEqual(deal.held_amount, Decimal("100.00"))
        self.assertEqual(deal.service_fee_amount, Decimal("7.00"))
        self.assertEqual(deal.buyer_amount, Decimal("107.00"))

    def test_seller_cannot_agree_without_phone(self):
        client = APIClient()
        client.force_authenticate(self.seller)

        response = client.post(f"/api/chats/{self.chat.pk}/agree/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("телефон", response.json()["detail"].lower())
        self.chat.refresh_from_db()
        self.assertEqual(self.chat.status, Chat.STATUS_PENDING)

    @patch("chats.views._create_cdek_order", return_value=("cdek-uuid", "CDEK-1"))
    def test_buyer_cannot_pay_without_phone(self, mock_cdek):
        self.seller.phone = "+79000000001"
        self.seller.delivery_point_code = "seller-pvz"
        self.seller.delivery_point_address = "Seller PVZ"
        self.seller.save(update_fields=["phone", "delivery_point_code", "delivery_point_address"])
        self.buyer.balance = Decimal("107.00")
        self.buyer.delivery_point_code = "buyer-pvz"
        self.buyer.delivery_point_address = "Buyer PVZ"
        self.buyer.save(update_fields=["balance", "delivery_point_code", "delivery_point_address"])
        self.chat.status = Chat.STATUS_AGREED
        self.chat.save(update_fields=["status"])

        client = APIClient()
        client.force_authenticate(self.buyer)
        response = client.post(f"/api/chats/{self.chat.pk}/pay/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("телефон", response.json()["detail"].lower())
        mock_cdek.assert_not_called()
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.balance, Decimal("107.00"))

    @patch("chats.views._create_cdek_order", return_value=("cdek-uuid", "CDEK-1"))
    def test_chat_pay_charges_buyer_total_and_holds_seller_amount(self, _mock_cdek):
        self.buyer.phone = "+79000000002"
        self.buyer.balance = Decimal("107.00")
        self.buyer.delivery_point_code = "buyer-pvz"
        self.buyer.delivery_point_address = "Buyer PVZ"
        self.buyer.save(update_fields=["phone", "balance", "delivery_point_code", "delivery_point_address"])
        self.seller.phone = "+79000000001"
        self.seller.delivery_point_code = "seller-pvz"
        self.seller.delivery_point_address = "Seller PVZ"
        self.seller.save(update_fields=["phone", "delivery_point_code", "delivery_point_address"])
        self.chat.status = Chat.STATUS_AGREED
        self.chat.save(update_fields=["status"])

        client = APIClient()
        client.force_authenticate(self.buyer)
        response = client.post(f"/api/chats/{self.chat.pk}/pay/")

        self.assertEqual(response.status_code, 200)
        self.buyer.refresh_from_db()
        self.chat.refresh_from_db()
        self.chat.deal.refresh_from_db()
        tx = Transaction.objects.get(user=self.buyer, kind=Transaction.EXPENSE)

        self.assertEqual(self.buyer.balance, Decimal("0.00"))
        self.assertEqual(tx.amount, Decimal("107.00"))
        self.assertEqual(self.chat.status, Chat.STATUS_PAID)
        self.assertEqual(self.chat.deal.amount, Decimal("100.00"))
        self.assertEqual(self.chat.deal.held_amount, Decimal("100.00"))
        self.assertEqual(self.chat.deal.service_fee_amount, Decimal("7.00"))
        self.assertEqual(self.chat.deal.buyer_amount, Decimal("107.00"))

    @patch("chats.views._create_cdek_order", return_value=("cdek-uuid", "CDEK-1"))
    def test_refund_returns_service_fee_to_buyer(self, _mock_cdek):
        self.buyer.phone = "+79000000002"
        self.buyer.balance = Decimal("107.00")
        self.buyer.delivery_point_code = "buyer-pvz"
        self.buyer.delivery_point_address = "Buyer PVZ"
        self.buyer.save(update_fields=["phone", "balance", "delivery_point_code", "delivery_point_address"])
        self.seller.phone = "+79000000001"
        self.seller.delivery_point_code = "seller-pvz"
        self.seller.delivery_point_address = "Seller PVZ"
        self.seller.save(update_fields=["phone", "delivery_point_code", "delivery_point_address"])
        self.chat.status = Chat.STATUS_AGREED
        self.chat.save(update_fields=["status"])

        client = APIClient()
        client.force_authenticate(self.buyer)
        response = client.post(f"/api/chats/{self.chat.pk}/pay/")
        self.assertEqual(response.status_code, 200)

        deal = self.chat.deal
        ok, _message = deal.refund_to_buyer(actor=self.seller)

        self.assertTrue(ok)
        self.buyer.refresh_from_db()
        deal.refresh_from_db()
        refund_tx = Transaction.objects.get(user=self.buyer, kind=Transaction.DEPOSIT)
        self.assertEqual(self.buyer.balance, Decimal("107.00"))
        self.assertEqual(refund_tx.amount, Decimal("107.00"))
        self.assertEqual(deal.escrow_status, Deal.ESCROW_REFUNDED_TO_BUYER)
