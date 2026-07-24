from django.test import Client as HttpClient, TestCase
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from notifications.services import notify, notify_all_clients, notify_staff_with_perm


class NotifyServiceTestCase(TestCase):
    """notify() هي أبسط نقطة دخول للنظام — إشعار لمستخدم واحد، مع قاعدة
    استثناء "الفاعل نفسه" (exclude_actor) عشان محدش ياخد إشعار بحدث عمله بنفسه."""

    def setUp(self):
        self.recipient = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )

    def test_notify_creates_notification(self):
        notification = notify(self.recipient, Notification.Kind.NEW_ORDER, 'عنوان تجريبي')
        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(notification.recipient, self.recipient)

    def test_notify_with_none_recipient_does_nothing(self):
        result = notify(None, Notification.Kind.NEW_ORDER, 'عنوان')
        self.assertIsNone(result)
        self.assertEqual(Notification.objects.count(), 0)

    def test_notify_skips_when_actor_is_recipient(self):
        result = notify(
            self.recipient, Notification.Kind.CLIENT_APPROVED_AMENDMENT, 'عنوان',
            exclude_actor=self.recipient,
        )
        self.assertIsNone(result)
        self.assertEqual(Notification.objects.count(), 0)

    def test_notify_does_not_skip_when_actor_is_different_user(self):
        other_user = User.objects.create_user(
            username='client2', email='client2@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        result = notify(
            self.recipient, Notification.Kind.ORDER_CONFIRMED, 'عنوان',
            exclude_actor=other_user,
        )
        self.assertIsNotNone(result)
        self.assertEqual(Notification.objects.count(), 1)


class NotifyStaffWithPermTestCase(TestCase):
    """
    بتبعت للموظفين اللي عندهم الصلاحية المطلوبة بس. الأدمن دايمًا مستلم
    (Superuser تلقائي)، والمخزن لازم يكون عنده الصلاحية صراحةً.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin1', email='admin1@example.com',
            password='testpass123', role=User.Role.ADMIN,
        )
        self.warehouse_with_perm = User.objects.create_user(
            username='warehouse1', email='warehouse1@example.com',
            password='testpass123', role=User.Role.WAREHOUSE,
        )
        self.warehouse_without_perm = User.objects.create_user(
            username='warehouse2', email='warehouse2@example.com',
            password='testpass123', role=User.Role.WAREHOUSE,
        )
        perm = 'orders.view_order'
        from django.contrib.auth.models import Permission
        app_label, codename = perm.split('.')
        permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
        self.warehouse_with_perm.user_permissions.add(permission)

    def test_admin_always_receives_notification(self):
        notify_staff_with_perm('orders.view_order', Notification.Kind.NEW_ORDER, 'طلب جديد')
        self.assertTrue(Notification.objects.filter(recipient=self.admin).exists())

    def test_warehouse_with_permission_receives_notification(self):
        notify_staff_with_perm('orders.view_order', Notification.Kind.NEW_ORDER, 'طلب جديد')
        self.assertTrue(Notification.objects.filter(recipient=self.warehouse_with_perm).exists())

    def test_warehouse_without_permission_does_not_receive_notification(self):
        notify_staff_with_perm('orders.view_order', Notification.Kind.NEW_ORDER, 'طلب جديد')
        self.assertFalse(Notification.objects.filter(recipient=self.warehouse_without_perm).exists())

    def test_excluded_actor_does_not_receive_notification(self):
        notify_staff_with_perm(
            'orders.view_order', Notification.Kind.NEW_ORDER, 'طلب جديد',
            exclude_actor=self.admin,
        )
        self.assertFalse(Notification.objects.filter(recipient=self.admin).exists())
        # لسه المخزن اللي عنده الصلاحية المفروض ياخد الإشعار عادي.
        self.assertTrue(Notification.objects.filter(recipient=self.warehouse_with_perm).exists())


class NotifyAllClientsTestCase(TestCase):
    """بتبعت لكل عميل نشط (status=ACTIVE)، مش العملاء المعلّقين أو المرفوضين."""

    def setUp(self):
        self.active_client = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT, status=User.Status.ACTIVE,
        )
        self.pending_client = User.objects.create_user(
            username='client2', email='client2@example.com',
            password='testpass123', role=User.Role.CLIENT, status=User.Status.PENDING,
        )

    def test_only_active_clients_receive_notification(self):
        notify_all_clients(Notification.Kind.NEW_ARRIVALS, 'وارد جديد')
        self.assertTrue(Notification.objects.filter(recipient=self.active_client).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.pending_client).exists())


class NotificationGetAbsoluteUrlTestCase(TestCase):
    def setUp(self):
        self.recipient = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )

    def test_valid_url_name_resolves(self):
        notification = Notification.objects.create(
            recipient=self.recipient, kind=Notification.Kind.NEW_ORDER,
            title='عنوان', url_name='notifications:list',
        )
        self.assertEqual(notification.get_absolute_url(), reverse('notifications:list'))

    def test_missing_url_name_returns_empty_string(self):
        notification = Notification.objects.create(
            recipient=self.recipient, kind=Notification.Kind.NEW_ORDER, title='عنوان',
        )
        self.assertEqual(notification.get_absolute_url(), '')

    def test_invalid_url_name_returns_empty_string_instead_of_crashing(self):
        notification = Notification.objects.create(
            recipient=self.recipient, kind=Notification.Kind.NEW_ORDER, title='عنوان',
            url_name='some:nonexistent-route',
        )
        self.assertEqual(notification.get_absolute_url(), '')


class NotificationViewsTestCase(TestCase):
    """اختبارات integration بسيطة على أهم مسارات الإشعارات: عدد غير المقروء،
    فتح إشعار (يعلّمه كمقروء ويودّي للوجهة)، وتحديد الكل كمقروء."""

    def setUp(self):
        self.http = HttpClient()
        self.user = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        self.http.login(username='client1', password='testpass123')

    def test_bell_data_returns_unread_count(self):
        Notification.objects.create(recipient=self.user, kind=Notification.Kind.NEW_ORDER, title='عنوان 1')
        Notification.objects.create(recipient=self.user, kind=Notification.Kind.NEW_ORDER, title='عنوان 2')
        response = self.http.get(reverse('notifications:bell_data'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['unread_count'], 2)

    def test_opening_notification_marks_it_read_and_redirects(self):
        notification = Notification.objects.create(
            recipient=self.user, kind=Notification.Kind.NEW_ORDER, title='عنوان',
            url_name='notifications:list',
        )
        response = self.http.get(reverse('notifications:open', args=[notification.pk]))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertEqual(response.status_code, 302)

    def test_cannot_open_another_users_notification(self):
        other_user = User.objects.create_user(
            username='client2', email='client2@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        notification = Notification.objects.create(
            recipient=other_user, kind=Notification.Kind.NEW_ORDER, title='عنوان',
        )
        response = self.http.get(reverse('notifications:open', args=[notification.pk]))
        self.assertEqual(response.status_code, 404)

    def test_mark_all_read(self):
        Notification.objects.create(recipient=self.user, kind=Notification.Kind.NEW_ORDER, title='عنوان 1')
        Notification.objects.create(recipient=self.user, kind=Notification.Kind.NEW_ORDER, title='عنوان 2')
        self.http.post(reverse('notifications:mark_all_read'))
        self.assertEqual(self.user.notifications.filter(is_read=False).count(), 0)
