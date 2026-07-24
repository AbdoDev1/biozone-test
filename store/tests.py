from decimal import Decimal

from django.test import Client as HttpClient, TestCase
from django.urls import reverse

from accounts.models import User
from inventory.models import Inventory
from products.models import Category, Product, ProductUnit


class StoreHomeNewArrivalsFilterTestCase(TestCase):
    """
    منتج "وارد جديد" (رصيده فوق الحد الأدنى وحديث الإضافة) لازم يظهر في
    صفحة الوارد بس ويتستبعد من الشبكة العادية، عشان الصنف ميظهرش في مكانين.
    """

    def setUp(self):
        self.http = HttpClient()
        self.category = Category.objects.create(name='مواد غذائية', slug='food')

        self.new_product = Product.objects.create(category=self.category, name_ar='منتج وارد')
        Inventory.objects.create(product=self.new_product, quantity=100, min_quantity=5)

        self.regular_product = Product.objects.create(category=self.category, name_ar='منتج عادي')
        Inventory.objects.create(product=self.regular_product, quantity=100, min_quantity=5)
        # نلغي وصفه كـ"وارد" يدويًا عشان يبقى منتج عادي في الاختبار.
        self.regular_product.new_arrival_at = None
        self.regular_product.save(update_fields=['new_arrival_at'])

    def test_new_arrival_product_excluded_from_store_home(self):
        response = self.http.get(reverse('store:home'))
        products = list(response.context['products'])
        self.assertNotIn(self.new_product, products)
        self.assertIn(self.regular_product, products)

    def test_new_arrival_product_appears_in_new_arrivals_page(self):
        self.http.force_login(
            User.objects.create_user(
                username='client1', email='client1@example.com',
                password='testpass123', role=User.Role.CLIENT,
            )
        )
        response = self.http.get(reverse('store:new_arrivals'))
        products = list(response.context['products'])
        self.assertIn(self.new_product, products)
        self.assertNotIn(self.regular_product, products)

    def test_low_stock_new_product_is_not_treated_as_new_arrival(self):
        # لو الرصيد نزل لحد الحد الأدنى أو تحته، الصنف بيرجع للمتجر العادي
        # حتى لو لسه حديث الإضافة زمنيًا.
        low_stock_product = Product.objects.create(category=self.category, name_ar='منتج قليل المخزون')
        Inventory.objects.create(product=low_stock_product, quantity=5, min_quantity=5)

        response = self.http.get(reverse('store:home'))
        products = list(response.context['products'])
        self.assertIn(low_stock_product, products)


class StoreHomeFilteringTestCase(TestCase):
    def setUp(self):
        self.http = HttpClient()
        self.category_a = Category.objects.create(name='أدوية', slug='meds')
        self.category_b = Category.objects.create(name='مستلزمات', slug='supplies')

        self.product_a = Product.objects.create(
            category=self.category_a, name_ar='بنادول', manufacturer='جلاكسو',
        )
        Inventory.objects.create(product=self.product_a, quantity=100, min_quantity=5)
        self.product_a.new_arrival_at = None
        self.product_a.save(update_fields=['new_arrival_at'])

        self.product_b = Product.objects.create(
            category=self.category_b, name_ar='شاش طبي', manufacturer='مصر',
        )
        Inventory.objects.create(product=self.product_b, quantity=100, min_quantity=5)
        self.product_b.new_arrival_at = None
        self.product_b.save(update_fields=['new_arrival_at'])

    def test_filter_by_category(self):
        response = self.http.get(reverse('store:home'), {'category': 'meds'})
        products = list(response.context['products'])
        self.assertEqual(products, [self.product_a])

    def test_filter_by_manufacturer(self):
        response = self.http.get(reverse('store:home'), {'manufacturer': 'مصر'})
        products = list(response.context['products'])
        self.assertEqual(products, [self.product_b])

    def test_search_by_name(self):
        response = self.http.get(reverse('store:home'), {'q': 'بنادول'})
        products = list(response.context['products'])
        self.assertEqual(products, [self.product_a])

    def test_inactive_products_are_excluded(self):
        self.product_a.is_active = False
        self.product_a.save(update_fields=['is_active'])
        response = self.http.get(reverse('store:home'))
        products = list(response.context['products'])
        self.assertNotIn(self.product_a, products)


class ProductDetailViewTestCase(TestCase):
    def setUp(self):
        self.http = HttpClient()
        category = Category.objects.create(name='أدوية', slug='meds')
        self.product = Product.objects.create(category=category, name_ar='بنادول')
        ProductUnit.objects.create(
            product=self.product, size=ProductUnit.Size.SMALL, name='قطعة',
            qty_in_small=1, unit_price=Decimal('10.00'),
        )

    def test_active_product_detail_returns_200(self):
        response = self.http.get(reverse('store:product_detail', args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)

    def test_inactive_product_returns_404(self):
        self.product.is_active = False
        self.product.save(update_fields=['is_active'])
        response = self.http.get(reverse('store:product_detail', args=[self.product.pk]))
        self.assertEqual(response.status_code, 404)

    def test_new_arrivals_requires_login(self):
        response = self.http.get(reverse('store:new_arrivals'))
        self.assertEqual(response.status_code, 302)
