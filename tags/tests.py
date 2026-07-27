"""
اختبارات مرحلة 4 (نظام الوسوم العام — ROADMAP.md): إضافة/إزالة وسم على
أي كيان، إعادة استخدام نفس الوسم بين كيانات مختلفة، وصلاحيات الوصول.
"""
from django.test import Client as HttpClient, TestCase
from django.urls import reverse

from accounts.models import User
from orders.models import Order
from products.models import Category, Product
from .models import Tag, TaggedItem
from .services import add_tag, remove_tag, tags_for


def make_staff(role=User.Role.WAREHOUSE):
    return User.objects.create_user(
        username=f'staff_{role.lower()}', email=f'{role.lower()}@example.com',
        password='testpass123', role=role,
    )


class TagServicesTestCase(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client1', email='client1@example.com', password='testpass123',
            role=User.Role.CLIENT,
        )
        self.order = Order.objects.create(client=self.client_user)
        category = Category.objects.create(name='مواد غذائية', slug='food')
        self.product = Product.objects.create(category=category, name_ar='منتج تجريبي')

    def test_add_tag_creates_tag_and_links_it(self):
        add_tag(self.order, 'عاجل', color='red')
        tag = Tag.objects.get(name='عاجل')
        self.assertEqual(tag.color, 'red')
        self.assertIn(tag, tags_for(self.order))

    def test_same_tag_name_is_reused_across_different_models(self):
        """نفس اسم الوسم على كيانين مختلفين (طلب ومنتج) لازم يشاور لنفس صف Tag."""
        add_tag(self.order, 'عاجل', color='red')
        add_tag(self.product, 'عاجل', color='blue')  # اللون هنا هيتجاهل لأن الوسم اتعمل بالفعل
        self.assertEqual(Tag.objects.filter(name='عاجل').count(), 1)
        tag = Tag.objects.get(name='عاجل')
        self.assertEqual(tag.color, 'red')
        self.assertIn(tag, tags_for(self.order))
        self.assertIn(tag, tags_for(self.product))

    def test_adding_same_tag_twice_does_not_duplicate_link(self):
        add_tag(self.order, 'عاجل')
        add_tag(self.order, 'عاجل')
        self.assertEqual(TaggedItem.objects.filter(tag__name='عاجل').count(), 1)

    def test_remove_tag_only_affects_target_item(self):
        tag = add_tag(self.order, 'عاجل')
        add_tag(self.product, 'عاجل')
        remove_tag(self.order, tag.pk)
        self.assertNotIn(tag, tags_for(self.order))
        self.assertIn(tag, tags_for(self.product))
        # الوسم نفسه يفضل موجود في النظام (مش بيتمسح) لاستخدامه على عناصر تانية
        self.assertTrue(Tag.objects.filter(pk=tag.pk).exists())

    def test_blank_tag_name_is_ignored(self):
        result = add_tag(self.order, '   ')
        self.assertIsNone(result)
        self.assertEqual(tags_for(self.order).count(), 0)


class TagViewsTestCase(TestCase):
    def setUp(self):
        self.http = HttpClient()
        self.client_user = User.objects.create_user(
            username='client1', email='client1@example.com', password='testpass123',
            role=User.Role.CLIENT,
        )
        self.order = Order.objects.create(client=self.client_user)

    def test_staff_can_add_tag_via_view(self):
        self.http.force_login(make_staff())
        self.http.post(
            reverse('tags:tag_add', args=['orders', 'order', self.order.pk]),
            {'name': 'يحتاج مراجعة', 'color': 'orange'},
        )
        self.assertIn('يحتاج مراجعة', [t.name for t in tags_for(self.order)])

    def test_client_cannot_add_tag(self):
        self.http.force_login(self.client_user)
        self.http.post(
            reverse('tags:tag_add', args=['orders', 'order', self.order.pk]),
            {'name': 'يحتاج مراجعة'},
        )
        self.assertEqual(tags_for(self.order).count(), 0)

    def test_staff_can_remove_tag_via_view(self):
        tag = add_tag(self.order, 'عاجل')
        self.http.force_login(make_staff())
        self.http.post(
            reverse('tags:tag_remove', args=['orders', 'order', self.order.pk, tag.pk]),
        )
        self.assertEqual(tags_for(self.order).count(), 0)

    def test_anonymous_redirected_to_login(self):
        response = self.http.post(
            reverse('tags:tag_add', args=['orders', 'order', self.order.pk]),
            {'name': 'عاجل'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(tags_for(self.order).count(), 0)
