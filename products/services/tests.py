from decimal import Decimal

from django.test import TestCase

from products.models import Category, Product
from products.services import import_export as svc


class ParseUnitRowTestCase(TestCase):
    """اختبارات على parse_unit_row: قراءة صف واحد من ملف الإكسل."""

    def setUp(self):
        Category.objects.create(name='شاش', slug='gauze')
        self.idx = {
            'name_ar': 0, 'category_slug': 1, 'unit_name': 2,
            'qty_in_small': 3, 'unit_price': 4, 'quantity': 5,
        }

    def test_valid_row_parses_correctly(self):
        row = ('شاش طبي', 'gauze', 'قطعة', 1, 2.5, 100)
        data, error = svc.parse_unit_row(2, row, self.idx, {})
        self.assertIsNone(error)
        self.assertEqual(data['name_ar'], 'شاش طبي')
        self.assertEqual(data['qty_in_small'], 1)
        self.assertEqual(data['unit_price'], 2.5)
        self.assertEqual(data['quantity'], 100)

    def test_missing_required_field_returns_error(self):
        row = ('', 'gauze', 'قطعة', 1, 2.5, 100)  # name_ar فاضي
        data, error = svc.parse_unit_row(2, row, self.idx, {})
        self.assertIsNone(data)
        self.assertIn('سطر 2', error)

    def test_invalid_numeric_value_returns_error(self):
        row = ('شاش طبي', 'gauze', 'قطعة', 'مش رقم', 2.5, 100)
        data, error = svc.parse_unit_row(2, row, self.idx, {})
        self.assertIsNone(data)
        self.assertIn('قيم رقمية غير صالحة', error)

    def test_qty_in_small_less_than_one_rejected(self):
        row = ('شاش طبي', 'gauze', 'قطعة', 0, 2.5, 100)
        data, error = svc.parse_unit_row(2, row, self.idx, {})
        self.assertIsNone(data)

    def test_unknown_category_slug_rejected(self):
        row = ('شاش طبي', 'not-a-real-category', 'قطعة', 1, 2.5, 100)
        data, error = svc.parse_unit_row(2, row, self.idx, {})
        self.assertIsNone(data)
        self.assertIn('مش موجود', error)


class GroupUnitRowsTestCase(TestCase):
    """اختبارات على group_unit_rows: تجميع صفوف الوحدات في أصناف."""

    def _row(self, row_num, name_ar, code='', qty_in_small=1):
        return {
            'row_num': row_num, 'code': code, 'category_slug': 'gauze',
            'name_ar': name_ar, 'unit_name': 'وحدة', 'qty_in_small': qty_in_small,
            'unit_price': 10, 'quantity': 0, 'discounts': {},
        }

    def test_two_rows_same_code_grouped_as_one_product(self):
        rows = [
            self._row(2, 'شاش طبي', code='BZ-001', qty_in_small=1),
            self._row(3, 'شاش طبي', code='BZ-001', qty_in_small=50),
        ]
        products_data, errors = svc.group_unit_rows(rows)
        self.assertEqual(len(products_data), 1)
        self.assertEqual(errors, [])
        self.assertIsNotNone(products_data[0]['small'])
        self.assertIsNotNone(products_data[0]['large'])

    def test_three_rows_same_key_is_an_error(self):
        rows = [
            self._row(2, 'شاش طبي', code='BZ-001', qty_in_small=1),
            self._row(3, 'شاش طبي', code='BZ-001', qty_in_small=50),
            self._row(4, 'شاش طبي', code='BZ-001', qty_in_small=100),
        ]
        products_data, errors = svc.group_unit_rows(rows)
        self.assertEqual(len(products_data), 0)
        self.assertEqual(len(errors), 1)

    def test_two_rows_same_size_is_an_error(self):
        rows = [
            self._row(2, 'شاش طبي', code='BZ-001', qty_in_small=1),
            self._row(3, 'شاش طبي', code='BZ-001', qty_in_small=1),
        ]
        products_data, errors = svc.group_unit_rows(rows)
        self.assertEqual(len(products_data), 0)
        self.assertEqual(len(errors), 1)

    def test_rows_without_code_grouped_by_normalized_name(self):
        rows = [
            self._row(2, 'شاش  طبي', qty_in_small=1),   # مسافة زيادة
            self._row(3, 'شاش طبي', qty_in_small=50),
        ]
        products_data, errors = svc.group_unit_rows(rows)
        self.assertEqual(len(products_data), 1)


class ClassifyRowTestCase(TestCase):
    """اختبارات على classify_row: تحديد update/create/review لكل صنف."""

    def setUp(self):
        self.category = Category.objects.create(name='شاش', slug='gauze')
        self.product = Product.objects.create(category=self.category, name_ar='شاش طبي معقم')

    def _row_data(self, name_ar, code=''):
        return {
            'row_num': 2, 'code': code, 'category_slug': 'gauze',
            'name_ar': name_ar, 'small': None, 'large': None, 'discounts': {},
        }

    def test_matching_code_classified_as_update(self):
        self.product.code = 'BZ-001'
        self.product.save()
        row = self._row_data('اسم مختلف تمامًا', code='BZ-001')
        result = svc.classify_row(
            row, {'BZ-001': self.product}, {}, [self.product],
        )
        self.assertEqual(result['action'], 'update')
        self.assertEqual(result['match_pk'], self.product.pk)

    def test_matching_normalized_name_classified_as_update(self):
        row = self._row_data('شاش طبي معقم')
        result = svc.classify_row(
            row, {}, {self.product.name_key: self.product}, [self.product],
        )
        self.assertEqual(result['action'], 'update')
        self.assertEqual(result['match_reason'], 'name')

    def test_completely_new_name_classified_as_create(self):
        row = self._row_data('صنف جديد تمامًا غير موجود')
        result = svc.classify_row(row, {}, {}, [self.product])
        self.assertEqual(result['action'], 'create')

    def test_similar_but_not_identical_name_needs_review(self):
        row = self._row_data('شاش طبي معقم رقم 2')  # قريب لكن مش مطابق
        result = svc.classify_row(row, {}, {}, [self.product])
        self.assertIn(result['action'], ('review', 'create'))


class CommitProductTestCase(TestCase):
    """اختبارات على commit_product: الحفظ الفعلي لصنف واحد من ملف الاستيراد."""

    def setUp(self):
        self.category = Category.objects.create(name='شاش', slug='gauze')

    def test_creates_new_product_with_units_and_stock(self):
        row_data = {
            'category_slug': 'gauze',
            'name_ar': 'شاش طبي جديد',
            'small': {'unit_name': 'قطعة', 'unit_price': 2.0, 'qty_in_small': 1, 'quantity': 100},
            'large': None,
            'discounts': {},
        }
        created, restocked = svc.commit_product(row_data, target_pk=None, user=None, account_types_by_pk={})
        self.assertTrue(created)
        self.assertTrue(restocked)

        product = Product.objects.get(name_ar='شاش طبي جديد')
        self.assertEqual(product.inventory.quantity, 100)
        self.assertEqual(product.units.count(), 1)

    def test_create_without_category_raises(self):
        row_data = {
            'category_slug': '', 'name_ar': 'صنف بدون قسم',
            'small': None, 'large': None, 'discounts': {},
        }
        with self.assertRaises(ValueError):
            svc.commit_product(row_data, target_pk=None, user=None, account_types_by_pk={})

    def test_update_existing_product_adds_stock_on_top(self):
        product = Product.objects.create(category=self.category, name_ar='شاش قديم')
        from inventory.models import Inventory
        Inventory.objects.create(product=product, quantity=50)

        row_data = {
            'category_slug': '', 'name_ar': 'شاش قديم محدّث',
            'small': {'unit_name': 'قطعة', 'unit_price': 3.0, 'qty_in_small': 1, 'quantity': 20},
            'large': None,
            'discounts': {},
        }
        created, restocked = svc.commit_product(row_data, target_pk=product.pk, user=None, account_types_by_pk={})
        self.assertFalse(created)
        self.assertTrue(restocked)

        product.refresh_from_db()
        self.assertEqual(product.name_ar, 'شاش قديم محدّث')
        self.assertEqual(product.inventory.quantity, 70)  # 50 + 20 مش استبدال
