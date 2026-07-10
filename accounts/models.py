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


class BusinessType(models.TextChoices):
    PHARMACY = 'PHARMACY', 'صيدلية'
    HOSPITAL = 'HOSPITAL', 'مستشفى'
    CLINIC = 'CLINIC', 'عيادة'
    OTHER = 'OTHER', 'أخرى'


class BusinessTypeSetting(models.Model):
    """
    إعداد افتراضي للتسعير على مستوى نوع النشاط (صيدلية/مستشفى/عيادة/أخرى).
    صف واحد لكل نوع — الأدمن بيحدد هل النوع ده جملة ولا قطاعي بشكل افتراضي،
    ولو جملة، نسبة الخصم المطبقة على unit_price لكل المنتجات.

    ده الإعداد الافتراضي بس — يقدر الأدمن يخصص حساب معين بغض النظر
    عن إعداد نوعه (شوف ClientProfile.is_wholesale_override).
    """
    business_type = models.CharField(
        max_length=20,
        choices=BusinessType.choices,
        unique=True,
    )
    is_wholesale = models.BooleanField(
        default=False,
        verbose_name='جملة افتراضيًا',
        help_text='لو مفعّل، أي حساب جديد من النوع ده هياخد سعر الجملة تلقائيًا.',
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='نسبة الخصم الافتراضية (%)',
        help_text='بتتطبق على سعر القطعة (unit_price) لو النوع ده جملة.',
    )

    class Meta:
        verbose_name = 'إعداد تسعير نوع النشاط'
        verbose_name_plural = 'إعدادات تسعير أنواع النشاط'

    def __str__(self):
        mode = f'جملة ({self.discount_percent}%)' if self.is_wholesale else 'قطاعي'
        return f'{self.get_business_type_display()} — {mode}'

    @classmethod
    def get_for(cls, business_type):
        """يرجع إعداد النوع، أو قيم افتراضية (قطاعي، 0%) لو مفيش صف متسجل لسه."""
        setting = cls.objects.filter(business_type=business_type).first()
        if setting:
            return setting
        return cls(business_type=business_type, is_wholesale=False, discount_percent=0)


class ClientProfile(models.Model):
    BusinessType = BusinessType  # يسهّل الوصول القديم عن طريق ClientProfile.BusinessType

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='client_profile',
    )
    business_name = models.CharField(max_length=255)
    business_type = models.CharField(
        max_length=20,
        choices=BusinessType.choices,
    )
    address = models.TextField()
    phone = models.CharField(max_length=20)
    verified_at = models.DateTimeField(null=True, blank=True)

    # --- تخصيص التسعير على مستوى الحساب (Override) ---
    # لو None: يتبع إعداد نوع النشاط (BusinessTypeSetting) تلقائيًا.
    # لو True/False: بيطغى على إعداد النوع لهذا الحساب بالتحديد فقط.
    is_wholesale_override = models.BooleanField(
        null=True, blank=True,
        verbose_name='تخصيص جملة/قطاعي لهذا الحساب',
        help_text='اترك هذا الحقل فارغًا إذا كان الحساب يتبع إعداد نوع النشاط تلقائيًا.',
    )
    custom_discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='نسبة خصم مخصصة لهذا الحساب (%)',
        help_text='اترك هذا الحقل فارغًا ليحصل الحساب على النسبة الافتراضية لنوع النشاط.',
    )

    def __str__(self):
        return f"{self.business_name} - {self.user.username}"

    def _business_type_setting(self):
        """
        كاش على مستوى الـ instance بس (مش global) — عشان صفحة المتجر اللي فيها
        20-30 منتج ما تضربش 40-60 استعلام على BusinessTypeSetting لنفس الصف
        بالظبط (نفس business_type لكل الحساب). لأن request.user.client_profile
        بيتكاش تلقائيًا على الـ user object طول الـ request، الكاش ده كافي.
        """
        if not hasattr(self, '_cached_business_type_setting'):
            self._cached_business_type_setting = BusinessTypeSetting.get_for(self.business_type)
        return self._cached_business_type_setting

    @property
    def is_wholesale(self):
        """هل الحساب ده جملة فعليًا؟ — الـ override بيطغى على إعداد النوع العام."""
        if self.is_wholesale_override is not None:
            return self.is_wholesale_override
        return self._business_type_setting().is_wholesale

    @property
    def effective_discount_percent(self):
        """نسبة الخصم الفعلية المطبقة — مخصصة لو موجودة، وإلا نسبة نوع النشاط."""
        if not self.is_wholesale:
            return 0
        if self.custom_discount_percent is not None:
            return self.custom_discount_percent
        return self._business_type_setting().discount_percent
