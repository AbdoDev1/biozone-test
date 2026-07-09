from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Employee, ClientProfile, BusinessTypeSetting


# =====================================================================
# الموظفين (مدير / مخزن) — منفصلة تمامًا عن العملاء.
# =====================================================================

class EmployeeChangeForm(forms.ModelForm):
    """
    نفس فورم التعديل الافتراضي بس بنقصر خيارات الدور على الموظفين فقط
    (مدير/مخزن) — عشان محدش يقدر يحول حساب من هنا لعميل بالغلط.
    """
    class Meta:
        model = Employee
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'role' in self.fields:
            self.fields['role'].choices = [
                (User.Role.ADMIN, 'مدير'),
                (User.Role.WAREHOUSE, 'مخزن'),
            ]


class EmployeeCreationForm(UserAdmin.add_form):
    """نفس فورم إضافة مستخدم جديد الافتراضي، بس بنقصر الدور على موظف بس."""
    class Meta(UserAdmin.add_form.Meta):
        model = Employee

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'role' in self.fields:
            self.fields['role'].choices = [
                (User.Role.ADMIN, 'مدير'),
                (User.Role.WAREHOUSE, 'مخزن'),
            ]
            self.fields['role'].initial = User.Role.WAREHOUSE
        if 'status' in self.fields:
            self.fields['status'].initial = User.Status.ACTIVE


@admin.register(Employee)
class EmployeeAdmin(UserAdmin):
    """
    شاشة إدارة الموظفين (مدير/مخزن) بس. حسابات العملاء متستخدش هنا خالص —
    شوف ClientProfileAdmin تحت لإدارة العملاء وصلاحياتهم.

    الصلاحيات الدقيقة (عرض/إضافة/تعديل/حذف لكل قسم) بقت بتتدار من لوحة
    الموظفين الخاصة بالنظام (staff panel → صلاحيات الموظفين) بواجهة عربية
    مبسّطة، مش من هنا — عشان كده مخفّين حقول is_superuser/groups/user_permissions
    التقنية من هنا (هي برضه بتتحدّث تلقائيًا: الأدمن Superuser دايمًا، شوف
    User.save()، وباقي الصلاحيات بتتحفظ في user_permissions من شاشة النظام
    مش من هنا لتفادي تعارض الاتنين).
    """
    form = EmployeeChangeForm
    add_form = EmployeeCreationForm
    list_display = ('username', 'email', 'role', 'status', 'is_active', 'permissions_note')
    list_filter = ('role', 'status')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('البيانات الشخصية', {'fields': ('first_name', 'last_name', 'email')}),
        ('بيانات الموظف', {'fields': ('role', 'status', 'is_active')}),
        ('تواريخ مهمة', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'status'),
        }),
    )

    def permissions_note(self, obj):
        if obj.role == User.Role.ADMIN:
            return 'وصول كامل (أدمن)'
        return 'من لوحة الموظفين — قسم صلاحيات الموظفين'
    permissions_note.short_description = 'الصلاحيات الدقيقة'

    def get_queryset(self, request):
        # نقصر القائمة على الموظفين بس، حتى لو حد ضاف عميل بالغلط من هنا
        # مش هيظهر تاني في القائمة دي.
        return super().get_queryset(request).filter(role__in=[User.Role.ADMIN, User.Role.WAREHOUSE])

    def save_model(self, request, obj, form, change):
        # أي حساب بيتضاف من شاشة الموظفين لازم يفضل موظف (مدير/مخزن)،
        # ومينفعش يبقى عميل حتى لو حصل تلاعب في البيانات المرسلة.
        if obj.role not in (User.Role.ADMIN, User.Role.WAREHOUSE):
            obj.role = User.Role.WAREHOUSE
        # الموظفين مش عندهم حالة "في الانتظار" زي العملاء، هما نشطين مباشرة
        if obj.status == User.Status.PENDING:
            obj.status = User.Status.ACTIVE
        super().save_model(request, obj, form, change)


# =====================================================================
# العملاء — شاشة منفصلة تمامًا، بدون أي صلاحية وصول للقسم المالي.
# =====================================================================

class ClientProfileForm(forms.ModelForm):
    """
    بنضيف حقلين مش موجودين أصلًا في ClientProfile (هما في User) عشان
    يبقى ممكن تفعيل/توقيف حساب العميل من نفس شاشة إعدادات العميل، بدل ما
    الأدمن يضطر يروح لشاشة تانية. القيم دي بتتحفظ على الـ user المرتبط.
    """
    account_status = forms.ChoiceField(
        choices=User.Status.choices,
        label='حالة الحساب',
        required=True,
    )
    is_active = forms.BooleanField(
        label='الحساب مفعّل (يقدر يسجّل دخول)',
        required=False,
    )

    class Meta:
        model = ClientProfile
        fields = (
            'user', 'business_name', 'business_type', 'address', 'phone', 'verified_at',
            'is_wholesale_override', 'custom_discount_percent',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user_id:
            self.fields['account_status'].initial = self.instance.user.status
            self.fields['is_active'].initial = self.instance.user.is_active

    def save(self, commit=True):
        profile = super().save(commit=False)
        if profile.user_id:
            profile.user.status = self.cleaned_data['account_status']
            profile.user.is_active = self.cleaned_data['is_active']
            # لوحة الإدارة بتنادي form.save(commit=False) دايمًا وبعدين بتحفظ
            # الـ profile بنفسها عن طريق save_model، فلازم نحفظ الـ user هنا
            # فورًا (مش بس لو commit=True) عشان التغييرات متضيعش.
            profile.user.save()
        if commit:
            profile.save()
        return profile


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    """
    شاشة إدارة العملاء وصلاحياتهم (تفعيل/إيقاف الحساب، وتخصيص جملة/قطاعي
    وخصم مخصص). منفصلة تمامًا عن شاشة الموظفين، ومفيهاش أي إشارة لصلاحية
    الوصول للقسم المالي لأن دي خاصة بالموظفين بس.
    """
    form = ClientProfileForm
    list_display = (
        'business_name', 'business_type', 'user', 'phone',
        'account_status_display', 'is_active_display',
        'is_wholesale', 'effective_discount_percent',
    )
    list_filter = ('business_type', 'user__status', 'user__is_active')
    search_fields = ('business_name', 'user__username', 'phone')
    actions = ['activate_accounts', 'deactivate_accounts']

    fields = (
        'user', 'business_name', 'business_type', 'address', 'phone', 'verified_at',
        'account_status', 'is_active',
        'is_wholesale_override', 'custom_discount_percent',
    )

    def is_wholesale(self, obj):
        return obj.is_wholesale
    is_wholesale.boolean = True
    is_wholesale.short_description = 'جملة؟'

    def account_status_display(self, obj):
        return obj.user.get_status_display()
    account_status_display.short_description = 'حالة الحساب'

    def is_active_display(self, obj):
        return obj.user.is_active
    is_active_display.boolean = True
    is_active_display.short_description = 'نشط؟'

    @admin.action(description='تفعيل الحسابات المحددة')
    def activate_accounts(self, request, queryset):
        count = 0
        for profile in queryset.select_related('user'):
            profile.user.status = User.Status.ACTIVE
            profile.user.is_active = True
            profile.user.save()
            count += 1
        self.message_user(request, f'تم تفعيل {count} حساب.')

    @admin.action(description='إيقاف الحسابات المحددة')
    def deactivate_accounts(self, request, queryset):
        count = 0
        for profile in queryset.select_related('user'):
            profile.user.is_active = False
            profile.user.save()
            count += 1
        self.message_user(request, f'تم إيقاف {count} حساب.')


@admin.register(User)
class BaseUserAdmin(admin.ModelAdmin):
    """
    تسجيل "مخفي" للموديل الأساسي User — مش بيظهر في قائمة لوحة الإدارة
    (شوف get_model_perms تحت)، وموجود بس عشان autocomplete_fields في
    AccountTransactionAdmin (حركات الحساب المالي) محتاجة موديل User
    مسجّل بـ search_fields. لإدارة الموظفين استخدم "الموظفين"، ولإدارة
    العملاء استخدم "العملاء" تحت.
    """
    search_fields = ['username', 'email']

    def get_model_perms(self, request):
        return {}


@admin.register(BusinessTypeSetting)
class BusinessTypeSettingAdmin(admin.ModelAdmin):
    list_display = ('get_business_type_display', 'is_wholesale', 'discount_percent')
    list_editable = ('is_wholesale', 'discount_percent')

    def get_business_type_display(self, obj):
        return obj.get_business_type_display()
    get_business_type_display.short_description = 'نوع النشاط'
