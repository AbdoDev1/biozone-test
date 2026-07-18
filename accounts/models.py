from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'مدير'
        WAREHOUSE = 'WAREHOUSE', 'مخزن'
        CLIENT = 'CLIENT', 'عميل'

    email = models.EmailField(unique=True, blank=False)

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
    )

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'في الانتظار'
        ACTIVE = 'ACTIVE', 'نشط'
        REJECTED = 'REJECTED', 'مرفوض'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    can_access_accounting = models.BooleanField(
        default=False,
        verbose_name='صلاحية الوصول للقسم المالي (قديم)',
        help_text='حقل قديم — استُبدل بنظام الصلاحيات الدقيق (staff.permissions.PERMISSION_SECTIONS). '
                   'اترك القيمة الافتراضية ومنّح صلاحية "الحسابات" من شاشة تعديل الموظف بدلًا منه.',
    )

    def save(self, *args, **kwargs):
        # الأدمن دايمًا Superuser تلقائيًا (وصول كامل لكل الصلاحيات بدون استثناء)،
        # وأي دور تاني (مخزن/عميل) مش Superuser أبدًا حتى لو اتغيّر يدويًا —
        # الدور هو مصدر الحقيقة الوحيد، مش حقل is_superuser نفسه.
        self.is_superuser = (self.role == self.Role.ADMIN)
        super().save(*args, **kwargs)

    def has_accounting_access(self):
        """
        الأدمن عنده وصول كامل تلقائيًا (Superuser بيرجع True من has_perm دايمًا).
        المخزن لازم يتاخد له صلاحية 'accounting.view_accounttransaction' صراحةً
        من شاشة تعديل الموظف (قسم الحسابات في كتالوج الصلاحيات).
        """
        return self.has_perm('accounting.view_accounttransaction')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class EmployeeManager(UserManager):
    """
    مدير خاص بيرجع الموظفين بس (مدير/مخزن) — بيتفصل عن العملاء تمامًا.
    مستخدم في لوحة الإدارة (Employee proxy) وفي أي مكان محتاج يتعامل مع
    الموظفين بدون ما يلمس حسابات العملاء بالغلط. بيورث من UserManager
    العادي (مش Manager) عشان يفضل عنده create_user/normalize_email
    وكل حاجة لازمة لفورمات لوحة الإدارة الخاصة بالمستخدمين.
    """
    def get_queryset(self):
        return super().get_queryset().filter(role__in=[User.Role.ADMIN, User.Role.WAREHOUSE])


class Employee(User):
    """
    Proxy model على User بيقصر النطاق على الموظفين (مدير/مخزن) بس.
    مستخدم عشان نفصل شاشة إدارة الموظفين في لوحة الإدارة عن شاشة العملاء،
    ونمنع ظهور صلاحية الوصول للقسم المالي لحسابات العملاء.
    """
    objects = EmployeeManager()

    class Meta:
        proxy = True
        verbose_name = 'موظف'
        verbose_name_plural = 'الموظفين'


class AccountType(models.Model):
    """
    نوع حساب العميل (جملة/صيدلية/مستشفى/...) — قائمة ديناميكية يديرها الأدمن
    فقط من لوحة الموظفين (مش من هنا مباشرة، ومش من Django admin). كل نوع
    بيحدد بس شكلين:
      1) الوحدة الافتراضية (صغرى/كبرى) اللي تظهر للعميل في المتجر.
      2) قائمة الخصومات لكل صنف/وحدة (شوف products.models.UnitDiscount) —
         مفيش خصم عام على مستوى الحساب أو النوع خالص، كل صنف له خصمه
         الخاص (أو بدون خصم لو مفيش صف متسجل).
    """
    class UnitSize(models.TextChoices):
        SMALL = 'S', 'صغرى'
        LARGE = 'L', 'كبرى'

    name = models.CharField(max_length=100, unique=True, verbose_name='اسم نوع الحساب')
    default_unit_size = models.CharField(
        max_length=1,
        choices=UnitSize.choices,
        default=UnitSize.SMALL,
        verbose_name='الوحدة الافتراضية',
        help_text='الوحدة (صغرى/كبرى) التي تظهر في المتجر لأي عميل من هذا النوع.',
    )
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'نوع حساب'
        verbose_name_plural = 'أنواع الحسابات'
        ordering = ['name']

    def __str__(self):
        return self.name


class ClientProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='client_profile',
    )
    business_name = models.CharField(max_length=255)
    account_type = models.ForeignKey(
        AccountType,
        on_delete=models.PROTECT,
        related_name='client_profiles',
        verbose_name='نوع الحساب',
        help_text='يحدد الوحدة الظاهرة في المتجر وقائمة الخصومات المطبّقة على هذا الحساب.',
    )
    address = models.TextField()
    phone = models.CharField(max_length=20)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.business_name} - {self.user.username}"
