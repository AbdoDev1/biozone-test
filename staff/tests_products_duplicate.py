"""
اختبارات مرحلة 4 (تكرار منتج — ROADMAP.md): نسخ منتج موجود (بوحداته)
كنقطة بداية بدل ملء فورم من الصفر.
"""
from decimal import Decimal

from django.test import Client as HttpClient, TestCase
from django.urls import reverse

from accounts.models import User
from activity.models import ActivityLog
from products.models import Category, Product, ProductUnit


def make_admin():
    return User.objects.create_user(
        username='admin1', email='admin1@example.com', password='testpass123',
        role=User.Role.ADMIN,
    )


class ProductDuplicateTestCase(TestCase):
    def setUp(self):
        self.http = HttpClient()
        self.http.force_login(make_admin())
        self.category = Category.objects.create(name='أدوية', slug='meds')
        self.source = Product.objects.create(
            category=self.category, name_ar='دواء تجريبي', name_en='Test Med',
            manufacturer='شركة تجريبية', barcode='123456789', is_active=True,
        )
        self.small_unit = ProductUnit.objects.create(
            product=self.source, size='S', name='قطعة', qty_in_small=1,
            unit_price=Decimal('10.00'), cost_price=Decimal('7.00'),
        )
        self.large_unit = ProductUnit.objects.create(
            product=self.source, size='L', name='كرتونة', qty_in_small=20,
            unit_price=Decimal('180.00'), cost_price=Decimal('130.00'),
        )

    def test_get_shows_confirmation_page_without_creating_anything(self):
        response = self.http.get(reverse('staff:product_duplicate', args=[self.source.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Product.objects.count(), 1)

    def test_post_creates_inactive_copy_with_same_units(self):
        response = self.http.post(reverse('staff:product_duplicate', args=[self.source.pk]))
        self.assertEqual(Product.objects.count(), 2)

        copy = Product.objects.exclude(pk=self.source.pk).get()
        self.assertEqual(copy.name_ar, f'{self.source.name_ar} (نسخة)')
        self.assertEqual(copy.name_en, self.source.name_en)
        self.assertEqual(copy.category_id, self.source.category_id)
        self.assertFalse(copy.is_active)  # النسخة تبدأ معطّلة لحد المراجعة

        self.assertEqual(copy.units.count(), 2)
        copy_small = copy.units.get(size='S')
        self.assertEqual(copy_small.unit_price, self.small_unit.unit_price)
        self.assertEqual(copy_small.cost_price, self.small_unit.cost_price)

        # يفوز الرد بالتوجيه لصفحة تعديل النسخة الجديدة مباشرة
        self.assertRedirects(response, reverse('staff:product_edit', args=[copy.pk]))

    def test_duplicate_does_not_copy_barcode(self):
        """الباركود فريد (unique) — النسخة الجديدة لازم تبدأ من غيره تمامًا."""
        response = self.http.post(reverse('staff:product_duplicate', args=[self.source.pk]))
        copy = Product.objects.exclude(pk=self.source.pk).get()
        self.assertIsNone(copy.barcode)
        # المنتج الأصلي يفضل زي ما هو من غير أي تأثير
        self.source.refresh_from_db()
        self.assertEqual(self.source.barcode, '123456789')

    def test_duplicate_logs_creation_activity_referencing_source(self):
        self.http.post(reverse('staff:product_duplicate', args=[self.source.pk]))
        copy = Product.objects.exclude(pk=self.source.pk).get()
        log = ActivityLog.objects.get(object_id=copy.pk, event=ActivityLog.Event.CREATED)
        self.assertIn(self.source.name_ar, log.note)
        self.assertIn(self.source.code, log.note)

    def test_duplicate_requires_add_product_permission(self):
        warehouse_user = User.objects.create_user(
            username='wh1', email='wh1@example.com', password='testpass123',
            role=User.Role.WAREHOUSE,
        )
        http = HttpClient()
        http.force_login(warehouse_user)
        response = http.post(reverse('staff:product_duplicate', args=[self.source.pk]))
        self.assertEqual(Product.objects.count(), 1)  # مفيش نسخة اتعملت
        self.assertNotEqual(response.status_code, 200)
