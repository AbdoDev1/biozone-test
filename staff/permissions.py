from django.contrib import messages
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.shortcuts import redirect

from accounts.models import User


def admin_required(view_func):
    """
    ديكوريتور للأقسام اللي لازم تتقصر على الأدمن حصريًا ومش قابلة للتفويض
    لموظف تاني عن طريق نظام الصلاحيات الدقيق تحت — تحديدًا شاشة إدارة
    الموظفين نفسها (إضافة/تعديل/منح صلاحيات)، عشان محدش غير الأدمن يقدر
    يمنح صلاحيات لنفسه أو لغيره (تصعيد صلاحيات).
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('staff:login')
        if request.user.role != User.Role.ADMIN:
            messages.error(request, 'هذه الصفحة متاحة للأدمن فقط.')
            return redirect('staff:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def perm_required(codename):
    """
    ديكوريتور بيتحقق من صلاحية دجانجو حقيقية (مثال: 'inventory.add_stockmovement').
    الأدمن Superuser تلقائيًا (شوف User.save) فـ has_perm بيرجعله True دايمًا،
    والمخزن لازم ياخد الصلاحية دي صراحةً من شاشة تعديل الموظف.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('staff:login')
            if request.user.role not in (User.Role.ADMIN, User.Role.WAREHOUSE):
                return redirect('staff:login')
            if not request.user.has_perm(codename):
                messages.error(request, 'ليس لديك صلاحية الوصول لهذا القسم. تواصل مع الأدمن.')
                return redirect('staff:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# =====================================================================
# كتالوج صلاحيات لوحة الموظفين
# =====================================================================
# كل صف هنا بيمثّل صلاحية دجانجو حقيقية موجودة أصلًا في auth.Permission
# (بتتولد تلقائيًا لكل موديل: add/change/delete/view) — إحنا بس بنعرضها
# بأسماء عربية مفهومة ومجمّعة حسب القسم، بدل شاشة Django admin التقنية
# اللي بتعرض كل صلاحيات النظام مبعثرة (زي اللي في لوحة الإدارة الافتراضية).
# لإضافة صلاحية جديدة لقسم: زوّد سطر هنا بس، مفيش أي migration مطلوبة
# لأن الصلاحيات دي جزء من نظام دجانجو الأساسي (auth app) أصلًا.
PERMISSION_SECTIONS = [
    {
        'key': 'inventory',
        'label': '📦 المخزون',
        'perms': [
            ('inventory', 'inventory', 'view', 'عرض المخزون'),
            ('inventory', 'stockmovement', 'add', 'تسجيل حركة مخزون (وارد/صادر)'),
        ],
    },
    {
        'key': 'orders',
        'label': '🧾 الطلبات',
        'perms': [
            ('orders', 'order', 'view', 'عرض الطلبات'),
            ('orders', 'order', 'change', 'تأكيد / رفض / تسليم / تعديل الطلبات'),
        ],
    },
    {
        'key': 'products',
        'label': '🛍️ المنتجات',
        'perms': [
            ('products', 'product', 'view', 'عرض المنتجات'),
            ('products', 'product', 'add', 'إضافة / استيراد منتجات'),
            ('products', 'product', 'change', 'تعديل منتج'),
            ('products', 'product', 'delete', 'حذف منتج'),
        ],
    },
    {
        'key': 'accounting',
        'label': '💰 الحسابات',
        'perms': [
            ('accounting', 'accounttransaction', 'view', 'عرض كشف الحسابات وتصديره'),
            ('accounting', 'accounttransaction', 'add', 'تسجيل دفعة / تسوية مالية'),
        ],
    },
    {
        'key': 'clients',
        'label': '👥 حسابات العملاء',
        'perms': [
            ('accounts', 'clientprofile', 'view', 'عرض حسابات العملاء'),
            ('accounts', 'clientprofile', 'change', 'الموافقة / الرفض / تعديل بيانات العميل'),
        ],
    },
]


def permission_codenames():
    """كل الصلاحيات المسموح منحها من الكتالوج، بصيغة 'app_label.action_model'."""
    return [
        f'{app}.{action}_{model}'
        for section in PERMISSION_SECTIONS
        for app, model, action, _ in section['perms']
    ]


def permissions_queryset_from_codenames(codenames):
    """
    بترجع QuerySet حقيقي من auth.Permission مطابق لقائمة codenames بصيغة
    'app_label.codename'. بنستخدمها وقت الحفظ عشان نربط user.user_permissions.
    """
    allowed = set(permission_codenames())
    codenames = [c for c in codenames if c in allowed]  # حماية: بس من الكتالوج المسموح بيه
    if not codenames:
        return Permission.objects.none()
    query = Q()
    for full in codenames:
        app_label, codename = full.split('.', 1)
        query |= Q(content_type__app_label=app_label, codename=codename)
    return Permission.objects.filter(query)


def grouped_permission_fields(employee=None):
    """
    بترجع الكتالوج جاهز للعرض في الفورم: كل قسم مع صلاحياته، وكل صلاحية
    معلّم عليها (checked) لو الموظف عنده أصلًا (أو لو أدمن، معلّمة الكل
    كملحوظة إن عنده وصول كامل تلقائيًا).
    """
    is_admin = bool(employee and employee.pk and employee.role == User.Role.ADMIN)
    user_codenames = set()
    if employee and employee.pk and not is_admin:
        user_codenames = {
            f'{p.content_type.app_label}.{p.codename}'
            for p in employee.user_permissions.select_related('content_type').all()
        }

    groups = []
    for section in PERMISSION_SECTIONS:
        items = []
        for app, model, action, label in section['perms']:
            full_codename = f'{app}.{action}_{model}'
            items.append({
                'codename': full_codename,
                'label': label,
                'checked': is_admin or full_codename in user_codenames,
            })
        groups.append({'key': section['key'], 'label': section['label'], 'items': items})
    return groups
