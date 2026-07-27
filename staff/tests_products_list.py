"""
اختبارات مرحلة 3 (ترقية جدول المنتجات — ROADMAP.md): ترتيب، فلترة
حالة/مخزون، تجميع حسب القسم، تفعيل/تعطيل جماعي، وتعديل السعر السريع
inline. ملف منفصل عن staff/tests.py (اللي مخصص لاختبارات template tags)
عشان الفصل بين نوعي الاختبار يفضل واضح.
"""
from decimal import Decimal

from django.test import Client as HttpClient, TestCase
from django.urls import reverse

from accounts.models import User
from activity.models import ActivityLog
from inventory.models import Inventory
from products.models import Category, Product, ProductUnit


def make_admin():
    return User.objects.create_user(
        username='admin1', email='admin1@example.com', password='testpass123',
        role=User.Role.ADMIN,
    )


class ProductListSortingTestCase(TestCase):
    def setUp(self):
        self.http = HttpClient()
        self.http.force_login(make_admin())
        self.category = Category.objects.create(name='أدوية', slug='meds')

        self.cheap = Product.objects.create(category=self.category, name_ar='صنف رخيص')
        ProductUnit.objects.create(product=self.cheap, size='S', name='قطعة', qty_in_small=1, unit_price=Decimal('10.00'))

        self.expensive = Product.objects.create(category=self.category, name_ar='صنف غالي')
        ProductUnit.objects.create(product=self.expensive, size='S', name='قطعة', qty_in_small=1, unit_price=Decimal('500.00'))

        self.no_unit = Product.objects.create(category=self.category, name_ar='صنف من غير وحدات')

    def test_sort_by_price_ascending_orders_by_smallest_unit_price(self):
        response = self.http.get(reverse('staff:product_list'), {'sort': 'price', 'dir': 'asc'})
        names = [p.name_ar for p in response.context['products']]
        # الصنف من غير وحدات (سعره None) المفروض يظهر، لكن الترتيب الأساسي
        # بين اللي عندهم سعر لازم يكون صحيح: رخيص قبل غالي.
        self.assertLess(names.index(self.cheap.name_ar), names.index(self.expensive.name_ar))

    def test_sort_by_price_descending_reverses_order(self):
        response = self.http.get(reverse('staff:product_list'), {'sort': 'price', 'dir': 'desc'})
        names = [p.name_ar for p in response.context['products']]
        self.assertLess(names.index(self.expensive.name_ar), names.index(self.cheap.name_ar))

    def test_invalid_sort_field_falls_back_to_name(self):
        response = self.http.get(reverse('staff:product_list'), {'sort': 'not_a_real_field'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sort'], 'name')

    def test_sort_links_render_with_arrow_indicator(self):
        response = self.http.get(reverse('staff:product_list'), {'sort': 'price', 'dir': 'asc'})
        self.assertContains(response, 'sort=price')
        self.assertContains(response, 'dir=desc')  # الرابط بيعرض الاتجاه العكسي (توگل)


class ProductListFilterTestCase(TestCase):
    def setUp(self):
        self.http = HttpClient()
        self.http.force_login(make_admin())
        self.category = Category.objects.create(name='أدوية', slug='meds')

        self.active_ok_stock = Product.objects.create(category=self.category, name_ar='نشط ومخزون كويس', is_active=True)
        Inventory.objects.create(product=self.active_ok_stock, quantity=100, reserved=0, min_quantity=5)

        self.active_low_stock = Product.objects.create(category=self.category, name_ar='نشط ومخزون منخفض', is_active=True)
        Inventory.objects.create(product=self.active_low_stock, quantity=3, reserved=0, min_quantity=5)

        self.inactive = Product.objects.create(category=self.category, name_ar='معطل', is_active=False)
        Inventory.objects.create(product=self.inactive, quantity=50, reserved=0, min_quantity=5)

        self.out_of_stock = Product.objects.create(category=self.category, name_ar='نافذ من المخزون', is_active=True)
        Inventory.objects.create(product=self.out_of_stock, quantity=2, reserved=2, min_quantity=5)

    def test_status_filter_active_excludes_inactive(self):
        response = self.http.get(reverse('staff:product_list'), {'status': 'active'})
        names = [p.name_ar for p in response.context['products']]
        self.assertNotIn(self.inactive.name_ar, names)
        self.assertIn(self.active_ok_stock.name_ar, names)

    def test_status_filter_inactive_returns_only_inactive(self):
        response = self.http.get(reverse('staff:product_list'), {'status': 'inactive'})
        names = [p.name_ar for p in response.context['products']]
        self.assertEqual(names, [self.inactive.name_ar])

    def test_stock_filter_low_matches_is_low_property(self):
        response = self.http.get(reverse('staff:product_list'), {'stock': 'low'})
        names = {p.name_ar for p in response.context['products']}
        self.assertIn(self.active_low_stock.name_ar, names)
        self.assertIn(self.out_of_stock.name_ar, names)
        self.assertNotIn(self.active_ok_stock.name_ar, names)

    def test_stock_filter_out_matches_zero_available(self):
        response = self.http.get(reverse('staff:product_list'), {'stock': 'out'})
        names = {p.name_ar for p in response.context['products']}
        self.assertIn(self.out_of_stock.name_ar, names)
        self.assertNotIn(self.active_low_stock.name_ar, names)

    def test_group_by_category_renders_category_header_row(self):
        response = self.http.get(reverse('staff:product_list'), {'group': '1'})
        self.assertTrue(response.context['group_by_category'])
        self.assertContains(response, self.category.name)


class ProductBulkActionTestCase(TestCase):
    def setUp(self):
        self.http = HttpClient()
        self.admin = make_admin()
        self.http.force_login(self.admin)
        category = Category.objects.create(name='أدوية', slug='meds')
        self.p1 = Product.objects.create(category=category, name_ar='صنف 1', is_active=True)
        self.p2 = Product.objects.create(category=category, name_ar='صنف 2', is_active=True)
        self.p3 = Product.objects.create(category=category, name_ar='صنف 3', is_active=False)

    def test_bulk_deactivate_updates_selected_products_only(self):
        self.http.post(reverse('staff:product_bulk_action'), {
            'product_ids': [self.p1.pk, self.p2.pk],
            'bulk_action': 'deactivate',
        })
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.p3.refresh_from_db()
        self.assertFalse(self.p1.is_active)
        self.assertFalse(self.p2.is_active)
        self.assertFalse(self.p3.is_active)  # كان معطل بالفعل، لسه معطل

    def test_bulk_activate_logs_activity_for_each_changed_product(self):
        self.http.post(reverse('staff:product_bulk_action'), {
            'product_ids': [self.p3.pk],
            'bulk_action': 'activate',
        })
        self.p3.refresh_from_db()
        self.assertTrue(self.p3.is_active)
        log_exists = ActivityLog.objects.filter(
            object_id=self.p3.pk, event=ActivityLog.Event.UPDATED,
        ).exists()
        self.assertTrue(log_exists)

    def test_bulk_action_with_no_ids_shows_warning_and_changes_nothing(self):
        response = self.http.post(reverse('staff:product_bulk_action'), {'bulk_action': 'deactivate'})
        self.p1.refresh_from_db()
        self.assertTrue(self.p1.is_active)
        self.assertEqual(response.status_code, 302)

    def test_already_matching_status_is_not_re_logged(self):
        # p1 نشط بالفعل — طلب "تفعيل" عليه مايسجلش نشاط جديد (مفيش تغيير حقيقي).
        count_before = ActivityLog.objects.filter(object_id=self.p1.pk).count()
        self.http.post(reverse('staff:product_bulk_action'), {
            'product_ids': [self.p1.pk],
            'bulk_action': 'activate',
        })
        count_after = ActivityLog.objects.filter(object_id=self.p1.pk).count()
        self.assertEqual(count_before, count_after)

    def test_get_request_is_rejected(self):
        response = self.http.get(reverse('staff:product_bulk_action'))
        self.assertEqual(response.status_code, 405)


class ProductQuickPriceEditTestCase(TestCase):
    def setUp(self):
        self.http = HttpClient()
        self.admin = make_admin()
        self.http.force_login(self.admin)
        category = Category.objects.create(name='أدوية', slug='meds')
        self.product = Product.objects.create(category=category, name_ar='صنف')
        self.unit = ProductUnit.objects.create(
            product=self.product, size='S', name='قطعة', qty_in_small=1, unit_price=Decimal('20.00'),
        )

    def test_valid_price_update_saves_and_returns_cell_partial(self):
        response = self.http.post(
            reverse('staff:product_quick_price', args=[self.unit.pk]),
            {'unit_price': '35.50'},
        )
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.unit_price, Decimal('35.50'))
        self.assertContains(response, '35.5')

    def test_price_update_logs_activity_with_old_and_new_value(self):
        self.http.post(
            reverse('staff:product_quick_price', args=[self.unit.pk]),
            {'unit_price': '99.00'},
        )
        log = ActivityLog.objects.filter(object_id=self.product.pk, event=ActivityLog.Event.UPDATED).first()
        self.assertIsNotNone(log)
        self.assertIn('20.00', log.changes_summary)
        self.assertIn('99.00', log.changes_summary)

    def test_invalid_price_value_does_not_save_and_returns_error(self):
        response = self.http.post(
            reverse('staff:product_quick_price', args=[self.unit.pk]),
            {'unit_price': 'not-a-number'},
        )
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.unit_price, Decimal('20.00'))
        self.assertContains(response, 'قيمة غير صحيحة')

    def test_negative_price_is_rejected(self):
        response = self.http.post(
            reverse('staff:product_quick_price', args=[self.unit.pk]),
            {'unit_price': '-5'},
        )
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.unit_price, Decimal('20.00'))
        self.assertContains(response, 'قيمة غير صحيحة')

    def test_same_price_does_not_create_a_new_activity_log(self):
        count_before = ActivityLog.objects.filter(object_id=self.product.pk).count()
        self.http.post(
            reverse('staff:product_quick_price', args=[self.unit.pk]),
            {'unit_price': '20.00'},
        )
        count_after = ActivityLog.objects.filter(object_id=self.product.pk).count()
        self.assertEqual(count_before, count_after)

    def test_get_request_is_rejected(self):
        response = self.http.get(reverse('staff:product_quick_price', args=[self.unit.pk]))
        self.assertEqual(response.status_code, 405)


class ProductListPermissionTestCase(TestCase):
    """الميزات الجديدة (bulk action, quick price) لازم تتحمي بنفس صلاحية
    products.change_product زي product_edit العادي — مش متاحة لمخزن من
    غير الصلاحية دي."""

    def setUp(self):
        self.http = HttpClient()
        self.warehouse_user = User.objects.create_user(
            username='wh1', email='wh1@example.com', password='testpass123',
            role=User.Role.WAREHOUSE,
        )
        self.http.force_login(self.warehouse_user)
        category = Category.objects.create(name='أدوية', slug='meds')
        self.product = Product.objects.create(category=category, name_ar='صنف')
        self.unit = ProductUnit.objects.create(
            product=self.product, size='S', name='قطعة', qty_in_small=1, unit_price=Decimal('20.00'),
        )

    def test_warehouse_without_change_permission_cannot_bulk_deactivate(self):
        response = self.http.post(reverse('staff:product_bulk_action'), {
            'product_ids': [self.product.pk], 'bulk_action': 'deactivate',
        })
        self.assertEqual(response.status_code, 302)  # اتحوّل بعيد (مرفوض)، مش نفّذ الإجراء
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)

    def test_warehouse_without_change_permission_cannot_quick_edit_price(self):
        response = self.http.post(
            reverse('staff:product_quick_price', args=[self.unit.pk]),
            {'unit_price': '99.00'},
        )
        self.assertEqual(response.status_code, 302)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.unit_price, Decimal('20.00'))
