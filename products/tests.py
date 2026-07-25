from decimal import Decimal

from django.test import TestCase

from accounts.models import AccountType, ClientProfile, User
from products.models import Category, Product, ProductUnit, UnitDiscount


def make_category(name='أدوية', slug='meds'):
    return Category.objects.create(name=name, slug=slug)


class ProductCodeGenerationTestCase(TestCase):
    """كود الصنف (BZ-00001...) لازم يكون فريد ومتسلسل، وميتغيرش لو المنتج
    اتحفظ تاني (مش بيتولّد إلا أول مرة)."""

    def setUp(self):
        self.category = make_category()

    def test_first_product_gets_code_00001(self):
        product = Product.objects.create(category=self.category, name_ar='منتج 1')
        self.assertEqual(product.code, 'BZ-00001')

    def test_second_product_gets_next_code(self):
        Product.objects.create(category=self.category, name_ar='منتج 1')
        second = Product.objects.create(category=self.category, name_ar='منتج 2')
        self.assertEqual(second.code, 'BZ-00002')

    def test_code_is_not_regenerated_on_update(self):
        product = Product.objects.create(category=self.category, name_ar='منتج 1')
        original_code = product.code
        product.name_ar = 'منتج 1 معدّل'
        product.save()
        self.assertEqual(product.code, original_code)

    def test_explicit_code_is_respected(self):
        product = Product.objects.create(category=self.category, name_ar='منتج مستورد', code='BZ-09999')
        self.assertEqual(product.code, 'BZ-09999')


class ProductNameNormalizationTestCase(TestCase):
    """name_key بيتحسب تلقائيًا وقت الحفظ عشان يستخدم في مطابقة الاستيراد
    من إكسل — لازم يوحّد الحروف المتشابهة شكليًا."""

    def setUp(self):
        self.category = make_category()

    def test_name_key_normalizes_hamza_variants(self):
        product = Product.objects.create(category=self.category, name_ar='أسبرين')
        self.assertEqual(product.name_key, 'اسبرين')

    def test_name_key_updates_when_name_changes(self):
        product = Product.objects.create(category=self.category, name_ar='بنادول')
        product.name_ar = 'بندول'
        product.save()
        self.assertEqual(product.name_key, 'بندول')


class ProductBarcodeTestCase(TestCase):
    """باركود فاضي لازم يتحول لـ None (مش '') عشان unique متعدد ميرفضش
    منتجات كتير من غير باركود."""

    def setUp(self):
        self.category = make_category()

    def test_blank_barcode_is_stored_as_none(self):
        product = Product.objects.create(category=self.category, name_ar='منتج', barcode='')
        self.assertIsNone(product.barcode)

    def test_whitespace_only_barcode_is_stored_as_none(self):
        product = Product.objects.create(category=self.category, name_ar='منتج', barcode='   ')
        self.assertIsNone(product.barcode)

    def test_multiple_products_without_barcode_do_not_conflict(self):
        Product.objects.create(category=self.category, name_ar='منتج 1', barcode='')
        Product.objects.create(category=self.category, name_ar='منتج 2', barcode='')
        self.assertEqual(Product.objects.count(), 2)


class ProductUnitsForClientTestCase(TestCase):
    """
    units_for_client هي اللي بتحدد للعميل يشوف الوحدة الصغرى ولا الكبرى في
    المتجر، حسب نوع حسابه — لازم تفضل ثابتة مهما اختلف ترتيب الوحدات
    في قاعدة البيانات.
    """

    def setUp(self):
        self.category = make_category()
        self.product = Product.objects.create(category=self.category, name_ar='منتج')
        self.small_unit = ProductUnit.objects.create(
            product=self.product, size=ProductUnit.Size.SMALL, name='قطعة',
            qty_in_small=1, unit_price=Decimal('10.00'),
        )
        self.large_unit = ProductUnit.objects.create(
            product=self.product, size=ProductUnit.Size.LARGE, name='كرتونة',
            qty_in_small=50, unit_price=Decimal('450.00'),
        )
        self.small_account_type = AccountType.objects.create(
            name='قطاعي', default_unit_size=AccountType.UnitSize.SMALL,
        )
        self.large_account_type, _ = AccountType.objects.get_or_create(
            name='جملة', defaults={'default_unit_size': AccountType.UnitSize.LARGE},
        )

    def _client_with_account_type(self, account_type, username):
        user = User.objects.create_user(
            username=username, email=f'{username}@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(
            user=user, business_name='محل', account_type=account_type,
            address='القاهرة', phone='01000000000',
        )
        return user

    def test_client_with_small_account_type_sees_small_unit(self):
        client = self._client_with_account_type(self.small_account_type, 'client_small')
        units = self.product.units_for_client(client)
        self.assertEqual(units, [self.small_unit])

    def test_client_with_large_account_type_sees_large_unit(self):
        client = self._client_with_account_type(self.large_account_type, 'client_large')
        units = self.product.units_for_client(client)
        self.assertEqual(units, [self.large_unit])

    def test_unauthenticated_or_no_profile_client_sees_small_unit(self):
        units = self.product.units_for_client(None)
        self.assertEqual(units, [self.small_unit])

    def test_product_without_units_returns_empty_list(self):
        empty_product = Product.objects.create(category=self.category, name_ar='منتج بدون وحدات')
        self.assertEqual(empty_product.units_for_client(None), [])

    def test_largest_and_smallest_unit_properties(self):
        self.assertEqual(self.product.largest_unit, self.large_unit)
        self.assertEqual(self.product.smallest_unit, self.small_unit)


class ProductUnitPricingTestCase(TestCase):
    """
    get_pricing_breakdown_for_account_type هي المصدر الوحيد للتسعير.
    الحالة الأهم: خصم الوحدة الكبرى (كرتونة) بيتشتق تلقائيًا من نسبة خصم
    القطعة (الوحدة الصغرى)، مش عن طريق ضرب سعر القطعة بعد الخصم في العدد.
    """

    def setUp(self):
        self.category = make_category()
        self.product = Product.objects.create(category=self.category, name_ar='منتج')
        self.small_unit = ProductUnit.objects.create(
            product=self.product, size=ProductUnit.Size.SMALL, name='قطعة',
            qty_in_small=1, unit_price=Decimal('10.00'),
        )
        self.large_unit = ProductUnit.objects.create(
            product=self.product, size=ProductUnit.Size.LARGE, name='كرتونة',
            qty_in_small=50, unit_price=Decimal('480.00'),
        )
        self.account_type, _ = AccountType.objects.get_or_create(name='جملة')

    def test_no_account_type_returns_public_price_without_discount(self):
        price, discount, final = self.small_unit.get_pricing_breakdown_for_account_type(None)
        self.assertEqual(price, Decimal('10.00'))
        self.assertEqual(discount, Decimal('0'))
        self.assertEqual(final, Decimal('10.00'))

    def test_no_discount_row_returns_public_price(self):
        price, discount, final = self.small_unit.get_pricing_breakdown_for_account_type(self.account_type)
        self.assertEqual(final, price)
        self.assertEqual(discount, Decimal('0'))

    def test_small_unit_discount_applies_directly(self):
        UnitDiscount.objects.create(
            unit=self.small_unit, account_type=self.account_type, discount_percent=Decimal('10.00'),
        )
        price, discount, final = self.small_unit.get_pricing_breakdown_for_account_type(self.account_type)
        self.assertEqual(price, Decimal('10.00'))
        self.assertEqual(discount, Decimal('10.00'))
        self.assertEqual(final, Decimal('9.00'))

    def test_large_unit_inherits_discount_percent_from_small_sibling(self):
        # الكرتونة بتاخد *نسبة* خصم القطعة، مطبّقة على سعر جمهور الكرتونة
        # نفسه (480) — مش ضرب سعر القطعة بعد الخصم (9.00) في qty_in_small (50).
        UnitDiscount.objects.create(
            unit=self.small_unit, account_type=self.account_type, discount_percent=Decimal('10.00'),
        )
        price, discount, final = self.large_unit.get_pricing_breakdown_for_account_type(self.account_type)
        self.assertEqual(price, Decimal('480.00'))
        self.assertEqual(discount, Decimal('10.00'))
        self.assertEqual(final, Decimal('432.00'))  # 480 * 0.9
        # تأكيد إن الحساب مش 9.00 * 50 = 450 (لأن ده هيكون غلط)
        self.assertNotEqual(final, Decimal('450.00'))

    def test_large_unit_without_small_sibling_discount_uses_own_discount_row(self):
        UnitDiscount.objects.create(
            unit=self.large_unit, account_type=self.account_type, discount_percent=Decimal('5.00'),
        )
        price, discount, final = self.large_unit.get_pricing_breakdown_for_account_type(self.account_type)
        self.assertEqual(discount, Decimal('5.00'))
        self.assertEqual(final, Decimal('456.00'))  # 480 * 0.95

    def test_get_price_returns_total_for_quantity(self):
        UnitDiscount.objects.create(
            unit=self.small_unit, account_type=self.account_type, discount_percent=Decimal('10.00'),
        )
        client = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(
            user=client, business_name='محل', account_type=self.account_type,
            address='القاهرة', phone='01000000000',
        )
        total = self.small_unit.get_price(qty=5, client=client)
        self.assertEqual(total, Decimal('45.00'))  # 9.00 * 5


class UnitDiscountTestCase(TestCase):
    def test_price_after_discount_rounds_to_two_decimals(self):
        category = make_category()
        product = Product.objects.create(category=category, name_ar='منتج')
        unit = ProductUnit.objects.create(
            product=product, size=ProductUnit.Size.SMALL, name='قطعة',
            qty_in_small=1, unit_price=Decimal('9.99'),
        )
        account_type, _ = AccountType.objects.get_or_create(name='جملة')
        discount = UnitDiscount.objects.create(
            unit=unit, account_type=account_type, discount_percent=Decimal('15.00'),
        )
        # 9.99 * 0.85 = 8.4915 -> يقرّب لـ 8.49
        self.assertEqual(discount.price_after_discount, Decimal('8.49'))
