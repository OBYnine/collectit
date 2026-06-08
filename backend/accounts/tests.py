from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from collectibles.models import Collection, Item
from .models import Transaction, WithdrawalRequest


User = get_user_model()


class WithdrawalRequestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="seller@example.com",
            username="seller",
            password="password",
            balance=Decimal("1000.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_sbp_withdrawal_reserves_balance(self):
        response = self.client.post("/api/accounts/withdrawals/", {
            "amount": "500.00",
            "method": WithdrawalRequest.METHOD_SBP,
            "full_name": "Иван Иванов",
            "phone": "+7 900 000 00 00",
            "bank_name": "Т-Банк",
        }, format="json")

        self.assertEqual(response.status_code, 201)
        self.user.refresh_from_db()
        withdrawal = WithdrawalRequest.objects.get(user=self.user)
        tx = Transaction.objects.get(user=self.user, kind=Transaction.EXPENSE)

        self.assertEqual(self.user.balance, Decimal("500.00"))
        self.assertEqual(withdrawal.amount, Decimal("500.00"))
        self.assertEqual(withdrawal.status, WithdrawalRequest.STATUS_PENDING)
        self.assertEqual(withdrawal.reserved_transaction, tx)
        self.assertEqual(tx.amount, Decimal("500.00"))
        self.assertEqual(response.json()["balance"], "500.00")

    def test_create_card_withdrawal_returns_masked_card(self):
        response = self.client.post("/api/accounts/withdrawals/", {
            "amount": "300.00",
            "method": WithdrawalRequest.METHOD_CARD,
            "full_name": "Иван Иванов",
            "card_number": "2200 0000 0000 1234",
            "card_holder": "IVAN IVANOV",
        }, format="json")

        self.assertEqual(response.status_code, 201)
        payload = response.json()["withdrawal"]
        self.assertNotIn("card_number", payload)
        self.assertEqual(payload["payout_details"]["card_number"], "**** **** **** 1234")

    def test_cannot_withdraw_more_than_balance(self):
        response = self.client.post("/api/accounts/withdrawals/", {
            "amount": "1500.00",
            "method": WithdrawalRequest.METHOD_SBP,
            "full_name": "Иван Иванов",
            "phone": "+79000000000",
            "bank_name": "Сбер",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("1000.00"))
        self.assertEqual(WithdrawalRequest.objects.count(), 0)

    def test_cannot_create_second_active_withdrawal(self):
        WithdrawalRequest.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            method=WithdrawalRequest.METHOD_SBP,
            full_name="Иван Иванов",
            phone="+79000000000",
            bank_name="Сбер",
        )

        response = self.client.post("/api/accounts/withdrawals/", {
            "amount": "200.00",
            "method": WithdrawalRequest.METHOD_CARD,
            "full_name": "Иван Иванов",
            "card_number": "2200000000001234",
            "card_holder": "IVAN IVANOV",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("1000.00"))

    def test_reject_and_refund_returns_reserved_amount(self):
        response = self.client.post("/api/accounts/withdrawals/", {
            "amount": "400.00",
            "method": WithdrawalRequest.METHOD_SBP,
            "full_name": "Иван Иванов",
            "phone": "+79000000000",
            "bank_name": "Сбер",
        }, format="json")
        self.assertEqual(response.status_code, 201)

        withdrawal = WithdrawalRequest.objects.get(user=self.user)
        ok, _message = withdrawal.reject_and_refund(actor=self.user)

        self.assertTrue(ok)
        self.user.refresh_from_db()
        withdrawal.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("1000.00"))
        self.assertEqual(withdrawal.status, WithdrawalRequest.STATUS_REJECTED)
        self.assertIsNotNone(withdrawal.refund_transaction_id)
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 2)


class OnboardingProgressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="collector@example.com",
            username="collector",
            password="password",
        )

    def test_completed_steps_do_not_roll_back_when_data_removed(self):
        self.user.phone = "+7 900 000 00 00"
        self.user.delivery_city = "Москва"
        self.user.delivery_point_code = "MSK1"
        self.user.delivery_point_address = "Москва, ул. Тверская, 12"
        self.user.save(update_fields=[
            "phone",
            "delivery_city",
            "delivery_point_code",
            "delivery_point_address",
        ])
        collection = Collection.objects.create(owner=self.user, name="Монеты")
        Item.objects.create(owner=self.user, collection=collection, name="1 рубль")

        self.user.sync_onboarding_progress()
        self.assertEqual(
            self.user.onboarding_completed_steps,
            ["phone", "delivery", "collection", "item"],
        )
        self.assertIsNotNone(self.user.onboarding_completed_at)

        self.user.phone = ""
        self.user.delivery_point_code = ""
        self.user.delivery_point_address = ""
        self.user.save(update_fields=["phone", "delivery_point_code", "delivery_point_address"])
        collection.delete()

        self.user.refresh_from_db()
        self.user.sync_onboarding_progress()
        self.assertEqual(
            self.user.onboarding_completed_steps,
            ["phone", "delivery", "collection", "item"],
        )

    def test_me_endpoint_persists_newly_completed_steps(self):
        self.user.phone = "+7 900 000 00 00"
        self.user.save(update_fields=["phone"])
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.get("/api/accounts/me/")

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.onboarding_completed_steps, ["phone"])
        self.assertEqual(response.json()["onboarding_completed_steps"], ["phone"])
