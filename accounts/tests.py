from django.contrib.auth.models import Permission
from django.test import TestCase

from accounts.models import AccountType, ClientProfile, Employee, User


class UserRolePrivilegeSyncTestCase(TestCase):
    """
    User.save() هي المصدر الوحيد اللي بيحدد is_superuser/is_staff من role —
    القاعدة دي أساسية أمنيًا: أدمن = Superuser دايمًا، وأي دور تاني (مخزن/عميل)
    مينفعش يبقى Superuser حتى لو اتغيّر يدويًا بعد كده.
    """

    def test_admin_role_grants_superuser_and_staff(self):
        user = User.objects.create_user(
            username='admin1', email='admin1@example.com',
            password='testpass123', role=User.Role.ADMIN,
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_warehouse_role_is_not_superuser_or_staff(self):
        user = User.objects.create_user(
            username='warehouse1', email='warehouse1@example.com',
            password='testpass123', role=User.Role.WAREHOUSE,
        )
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_client_role_is_not_superuser_or_staff(self):
        user = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_demoting_admin_to_warehouse_revokes_superuser(self):
        # حالة تصعيد/تنزيل الدور — لازم الصلاحيات تتحدّث فورًا، مش تفضل
        # عالقة من الدور القديم.
        user = User.objects.create_user(
            username='admin1', email='admin1@example.com',
            password='testpass123', role=User.Role.ADMIN,
        )
        self.assertTrue(user.is_superuser)
        user.role = User.Role.WAREHOUSE
        user.save()
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_manually_setting_superuser_true_on_non_admin_is_overridden(self):
        # حتى لو حد حاول يحط is_superuser=True يدويًا على مخزن/عميل، الدور
        # هو مصدر الحقيقة الوحيد ولازم يرجّعها False وقت الحفظ.
        user = User.objects.create_user(
            username='warehouse1', email='warehouse1@example.com',
            password='testpass123', role=User.Role.WAREHOUSE,
        )
        user.is_superuser = True
        user.save()
        self.assertFalse(user.is_superuser)


class UserAccountingAccessTestCase(TestCase):
    """has_accounting_access() بترجع True للأدمن دايمًا، وللمخزن بس لو معاه
    صلاحية 'accounting.view_accounttransaction' صراحةً."""

    def test_admin_has_accounting_access_by_default(self):
        admin = User.objects.create_user(
            username='admin1', email='admin1@example.com',
            password='testpass123', role=User.Role.ADMIN,
        )
        self.assertTrue(admin.has_accounting_access())

    def test_warehouse_without_permission_has_no_accounting_access(self):
        warehouse = User.objects.create_user(
            username='warehouse1', email='warehouse1@example.com',
            password='testpass123', role=User.Role.WAREHOUSE,
        )
        self.assertFalse(warehouse.has_accounting_access())

    def test_warehouse_with_permission_has_accounting_access(self):
        warehouse = User.objects.create_user(
            username='warehouse1', email='warehouse1@example.com',
            password='testpass123', role=User.Role.WAREHOUSE,
        )
        permission = Permission.objects.get(
            content_type__app_label='accounting', codename='view_accounttransaction',
        )
        warehouse.user_permissions.add(permission)
        # has_perm بيعتمد على كاش داخلي على الـ instance، فبنجيب نسخة جديدة.
        warehouse = User.objects.get(pk=warehouse.pk)
        self.assertTrue(warehouse.has_accounting_access())

    def test_client_has_no_accounting_access(self):
        client_user = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        self.assertFalse(client_user.has_accounting_access())


class EmployeeManagerTestCase(TestCase):
    """Employee (proxy model) لازم يرجّع الموظفين (أدمن/مخزن) بس، ومايظهرش فيها أي عميل."""

    def test_employee_queryset_excludes_clients(self):
        User.objects.create_user(
            username='admin1', email='admin1@example.com',
            password='testpass123', role=User.Role.ADMIN,
        )
        User.objects.create_user(
            username='warehouse1', email='warehouse1@example.com',
            password='testpass123', role=User.Role.WAREHOUSE,
        )
        User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        usernames = set(Employee.objects.values_list('username', flat=True))
        self.assertEqual(usernames, {'admin1', 'warehouse1'})


class ClientProfileTestCase(TestCase):
    def test_client_profile_str_includes_business_name_and_username(self):
        account_type, _ = AccountType.objects.get_or_create(name='جملة')
        user = User.objects.create_user(
            username='client1', email='client1@example.com',
            password='testpass123', role=User.Role.CLIENT,
        )
        profile = ClientProfile.objects.create(
            user=user, business_name='محل الأمانة', account_type=account_type,
            address='القاهرة', phone='01000000000',
        )
        self.assertIn('محل الأمانة', str(profile))
        self.assertIn('client1', str(profile))
