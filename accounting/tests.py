from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import AccountTransaction
from accounts.models import User


class AccountTransactionValidationTestCase(TestCase):
    """
    اختبارات على قيود clean() في AccountTransaction: كل نوع حركة (فاتورة/دفعة)
    لازم تتقفل على إشارة (موجب/سالب) معيّنة، عشان balance_for يفضل معناها
    صحيح دايمًا (مديونية العميل = مجموع amount).
    """

    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client1',
            email='client1@example.com',
            password='testpass123',
            role=User.Role.CLIENT,
        )

    def test_invoice_transaction_requires_positive_amount(self):
        with self.assertRaises(ValidationError):
            AccountTransaction.objects.create(
                client=self.client_user,
                kind=AccountTransaction.Kind.INVOICE,
                amount=Decimal('-50.00'),
            )

    def test_invoice_transaction_rejects_zero_amount(self):
        with self.assertRaises(ValidationError):
            AccountTransaction.objects.create(
                client=self.client_user,
                kind=AccountTransaction.Kind.INVOICE,
                amount=Decimal('0'),
            )

    def test_payment_transaction_requires_negative_amount(self):
        with self.assertRaises(ValidationError):
            AccountTransaction.objects.create(
                client=self.client_user,
                kind=AccountTransaction.Kind.PAYMENT,
                amount=Decimal('50.00'),
            )

    def test_payment_transaction_rejects_zero_amount(self):
        with self.assertRaises(ValidationError):
            AccountTransaction.objects.create(
                client=self.client_user,
                kind=AccountTransaction.Kind.PAYMENT,
                amount=Decimal('0'),
            )

    def test_adjustment_transaction_allows_any_sign(self):
        # التسوية (ADJUSTMENT) مالهاش قيد إشارة في clean() — لازم تتقبل
        # موجب وسالب من غير استثناء.
        AccountTransaction.objects.create(
            client=self.client_user,
            kind=AccountTransaction.Kind.ADJUSTMENT,
            amount=Decimal('-25.00'),
        )
        AccountTransaction.objects.create(
            client=self.client_user,
            kind=AccountTransaction.Kind.ADJUSTMENT,
            amount=Decimal('25.00'),
        )
        self.assertEqual(AccountTransaction.objects.count(), 2)

    def test_valid_invoice_and_payment_save_successfully(self):
        AccountTransaction.objects.create(
            client=self.client_user,
            kind=AccountTransaction.Kind.INVOICE,
            amount=Decimal('300.00'),
        )
        AccountTransaction.objects.create(
            client=self.client_user,
            kind=AccountTransaction.Kind.PAYMENT,
            amount=Decimal('-100.00'),
        )
        self.assertEqual(AccountTransaction.objects.count(), 2)


class AccountTransactionBalanceTestCase(TestCase):
    """
    balance_for هي المصدر الوحيد لحساب مديونية العميل في كل الشاشات
    (كشف الحساب، تقارير الديون...) — لازم تفضل بتحسب صح مهما اختلف
    عدد/نوع الحركات.
    """

    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client1',
            email='client1@example.com',
            password='testpass123',
            role=User.Role.CLIENT,
        )
        self.other_client = User.objects.create_user(
            username='client2',
            email='client2@example.com',
            password='testpass123',
            role=User.Role.CLIENT,
        )

    def test_balance_with_no_transactions_is_zero(self):
        self.assertEqual(AccountTransaction.balance_for(self.client_user), 0)

    def test_balance_accumulates_invoices_and_payments(self):
        AccountTransaction.objects.create(
            client=self.client_user, kind=AccountTransaction.Kind.INVOICE,
            amount=Decimal('500.00'),
        )
        AccountTransaction.objects.create(
            client=self.client_user, kind=AccountTransaction.Kind.INVOICE,
            amount=Decimal('200.00'),
        )
        AccountTransaction.objects.create(
            client=self.client_user, kind=AccountTransaction.Kind.PAYMENT,
            amount=Decimal('-300.00'),
        )
        self.assertEqual(AccountTransaction.balance_for(self.client_user), Decimal('400.00'))

    def test_balance_is_scoped_per_client(self):
        AccountTransaction.objects.create(
            client=self.client_user, kind=AccountTransaction.Kind.INVOICE,
            amount=Decimal('500.00'),
        )
        AccountTransaction.objects.create(
            client=self.other_client, kind=AccountTransaction.Kind.INVOICE,
            amount=Decimal('999.00'),
        )
        self.assertEqual(AccountTransaction.balance_for(self.client_user), Decimal('500.00'))
        self.assertEqual(AccountTransaction.balance_for(self.other_client), Decimal('999.00'))

    def test_adjustment_can_bring_balance_to_zero_or_negative(self):
        AccountTransaction.objects.create(
            client=self.client_user, kind=AccountTransaction.Kind.INVOICE,
            amount=Decimal('200.00'),
        )
        AccountTransaction.objects.create(
            client=self.client_user, kind=AccountTransaction.Kind.ADJUSTMENT,
            amount=Decimal('-250.00'),
        )
        self.assertEqual(AccountTransaction.balance_for(self.client_user), Decimal('-50.00'))
