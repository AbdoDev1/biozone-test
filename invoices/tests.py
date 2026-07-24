from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import AccountTransaction
from accounts.models import User
from inventory.models import Inventory
from invoices.models import Invoice, InvoiceItem, InvoiceSequence
from invoices.utils import amount_to_arabic_words
from orders.models import Order, OrderItem
from products.models import Category, Product, ProductUnit


class InvoiceSequenceTestCase(TestCase):
    """
    next_number لازم يبقى تسلسلي، بدون تكرار، ومنفصل تمامًا بين السنين
    المختلفة (كل سنة عندها عدادها الخاص من الصفر).
    """

    def test_first_number_for_a_year_is_one(self):
        self.assertEqual(InvoiceSequence.next_number(2026), 1)

    def test_numbers_increment_sequentially(self):
        self.assertEqual(InvoiceSequence.next_number(2026), 1)
        self.assertEqual(InvoiceSequence.next_number(2026), 2)
        self.assertEqual(InvoiceSequence.next_number(2026), 3)

    def test_each_year_has_independent_sequence(self):
        self.assertEqual(InvoiceSequence.next_number(2025), 1)
        self.assertEqual(InvoiceSequence.next_number(2025), 2)
        # سنة جديدة لازم تبدأ من 1 برضه، مش تكمل من 2025.
        self.assertEqual(InvoiceSequence.next_number(2026), 1)


class InvoiceImmutabilityTestCase(TestCase):
    """
    الفاتورة وصنفها مستندات immutable بعد الإصدار — دي قاعدة محاسبية
    أساسية في النظام (أي تصحيح = مستند مرتجع منفصل، مش تعديل مباشر).
    """

    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        self.order = Order.objects.create(client=self.client_user)
        self.invoice = Invoice.objects.create(
            invoice_number='INV-2026-000001',
            order=self.order,
            client_name='عميل تجريبي',
            total=Decimal('100.00'),
        )

    def test_editing_existing_invoice_raises(self):
        self.invoice.total = Decimal('999.00')
        with self.assertRaises(ValidationError):
            self.invoice.save()

    def test_deleting_invoice_raises(self):
        with self.assertRaises(ValidationError):
            self.invoice.delete()

    def test_editing_existing_invoice_item_raises(self):
        item = InvoiceItem.objects.create(
            invoice=self.invoice, product_name='منتج', unit_name='قطعة',
            quantity=5, public_price=Decimal('10.00'), unit_price=Decimal('10.00'),
        )
        item.quantity = 999
        with self.assertRaises(ValidationError):
            item.save()

    def test_deleting_invoice_item_raises(self):
        item = InvoiceItem.objects.create(
            invoice=self.invoice, product_name='منتج', unit_name='قطعة',
            quantity=5, public_price=Decimal('10.00'), unit_price=Decimal('10.00'),
        )
        with self.assertRaises(ValidationError):
            item.delete()


class InvoiceItemCalculationsTestCase(TestCase):
    """subtotal/public_subtotal/discount_amount لازم تعكس الفرق بين سعر
    الجمهور وسعر ما بعد الخصم بالظبط، لأنها هي اللي بتتطبع على الفاتورة."""

    def test_amounts_with_discount(self):
        invoice = Invoice.objects.create(
            invoice_number='INV-2026-000002',
            order=Order.objects.create(client=User.objects.create_user(
                username='client2', email='client2@example.com',
                password='testpass123', role=User.Role.CLIENT,
            )),
            client_name='عميل تجريبي',
            total=Decimal('180.00'),
        )
        item = InvoiceItem.objects.create(
            invoice=invoice, product_name='منتج', unit_name='قطعة',
            quantity=10, public_price=Decimal('20.00'),
            discount_percent=Decimal('10.00'), unit_price=Decimal('18.00'),
        )
        self.assertEqual(item.public_subtotal, Decimal('200.00'))
        self.assertEqual(item.subtotal, Decimal('180.00'))
        self.assertEqual(item.discount_amount, Decimal('20.00'))


class IssueForOrderTestCase(TestCase):
    """
    issue_for_order هي نقطة الوصل بين الطلبات والحسابات: بتولّد الفاتورة
    *و* حركة الحساب (AccountTransaction) في نفس العملية. أي كسر هنا معناه
    عميل اتسلمله بضاعة من غير ما تتسجل عليه مديونية، أو العكس.
    """

    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client3', email='client3@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        category = Category.objects.create(name='مواد غذائية', slug='food')
        self.product = Product.objects.create(category=category, name_ar='منتج تجريبي')
        self.unit = ProductUnit.objects.create(
            product=self.product, size=ProductUnit.Size.SMALL, name='قطعة',
            qty_in_small=1, unit_price=Decimal('15.00'),
        )
        Inventory.objects.create(product=self.product, quantity=50, min_quantity=5)
        self.order = Order.objects.create(client=self.client_user)
        OrderItem.objects.create(
            order=self.order, product_unit=self.unit, quantity=4,
            public_price=self.unit.unit_price, unit_price=self.unit.unit_price,
        )

    def test_issue_for_order_creates_invoice_with_items(self):
        invoice = Invoice.issue_for_order(self.order, actor=self.client_user)
        self.assertEqual(invoice.total, self.order.total)
        self.assertEqual(invoice.items.count(), 1)
        self.assertTrue(invoice.invoice_number.startswith(f'INV-{self.order.updated_at.year}-'))

    def test_issue_for_order_creates_account_transaction(self):
        invoice = Invoice.issue_for_order(self.order, actor=self.client_user)
        txn = AccountTransaction.objects.get(invoice=invoice)
        self.assertEqual(txn.kind, AccountTransaction.Kind.INVOICE)
        self.assertEqual(txn.amount, invoice.total)
        self.assertEqual(AccountTransaction.balance_for(self.client_user), invoice.total)

    def test_issue_for_order_is_idempotent(self):
        first = Invoice.issue_for_order(self.order)
        second = Invoice.issue_for_order(self.order)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.filter(invoice=first).count(), 1)


class AmountToArabicWordsTestCase(TestCase):
    """دالة نصية بحتة بتتطبع على كل فاتورة — عايزين نتأكد إنها بترجع
    صيغة سليمة للحالات الشائعة (مبلغ صحيح، فيه قروش، صفر)."""

    def test_whole_pounds_only(self):
        result = amount_to_arabic_words(Decimal('100.00'))
        self.assertIn('فقط', result)
        self.assertIn('جنيهاً', result)
        self.assertIn('لا غير', result)
        self.assertNotIn('قرشاً', result)

    def test_pounds_with_piastres(self):
        result = amount_to_arabic_words(Decimal('219.40'))
        self.assertIn('جنيهاً', result)
        self.assertIn('قرشاً', result)
        self.assertIn('لا غير', result)

    def test_zero_amount_does_not_crash(self):
        result = amount_to_arabic_words(Decimal('0.00'))
        self.assertIn('فقط', result)
        self.assertIn('لا غير', result)
