"""
"الوارد الجديد" — منتجات اتضافت لأول مرة أو اتزوّد رصيدها، ولسه رصيدها
الحالي فوق الحد الأدنى (Inventory.min_quantity). الاختيار التصميمي هنا
مقصود: مفيش موديل أو جدول منفصل لـ"الوارد"، ومفيش نسخ مكرّرة من بيانات
المنتج — هي نفس صفوف Product بالظبط. "الوارد" مجرد فلتر (Q) بيتحسب من
new_arrival_at + المخزون، وبيستخدم في مكانين:

1) badge على كارت المنتج في المتجر العادي (store/views.store_home) —
   الصنف فاضل ظاهر في الشبكة/البحث/الأقسام زي أي منتج تاني بالظبط، وبس
   عليه علامة "وارد جديد".
2) صفحة "الوارد" (store:new_arrivals) اللي بتجمع كل الأصناف دي في مكان
   واحد، بنفس بحث/فلاتر المتجر العادي.

الصنف بيخرج من حالة "وارد" (تختفي العلامة، ويختفي من صفحة الوارد، لكنه
يفضل ظاهر في المتجر العادي زي ما هو) أول ما أي شرط من الاتنين يتحقق:

1) الكمية: الرصيد (Inventory.quantity) وصل الحد الأدنى المحدد للصنف —
   يعني اتهلك بما يكفي إنه مابقاش "زيادة عن اللزوم" في السوق.
2) الوقت: NEW_ARRIVALS_WINDOW_DAYS يوم عدّوا من new_arrival_at — شبكة
   أمان عشان صنف بطيء الحركة (رصيده مانزلش) ميفضلش عالق في الوارد
   للأبد لو محدش اشتراه.

الفايدة: مصدر حقيقة واحد (source of truth واحد)، صفر تكلفة صيانة
إضافية، وبتتوسّع عادي (فلتر على حقول مفهرسة/مربوطة) حتى لو الكتالوج كبر.
"""
from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from .models import Product

NEW_ARRIVALS_WINDOW_DAYS = 7


def new_arrival_filter():
    """
    Q بيمثّل شرط "وارد جديد" (الوقت + المخزون) لوحده، من غير أي
    select_related/prefetch/order_by — عشان يتستخدم زي ما هو في مكانين
    مختلفين: annotate على شبكة المتجر العادية (badge)، وفلترة مباشرة في
    new_arrivals_queryset (صفحة الوارد).

    منتج من غير سجل مخزون (Inventory) أصلاً معندوش رصيد يتقاس، فبيتستبعد
    تلقائيًا (inner join عادي بيرجع بس المنتجات اللي ليها Inventory).
    """
    cutoff = timezone.now() - timedelta(days=NEW_ARRIVALS_WINDOW_DAYS)
    return Q(new_arrival_at__gte=cutoff) & Q(inventory__quantity__gt=F('inventory__min_quantity'))


def new_arrivals_queryset():
    """
    كل المنتجات النشطة اللي مستوفية new_arrival_filter — مستخدمة في صفحة
    "الوارد" (store:new_arrivals) وفي شريط عدد الإشعارات
    (store/context_processors.new_arrivals_count).
    """
    return (
        Product.objects.filter(is_active=True)
        .filter(new_arrival_filter())
        .select_related('category', 'inventory')
        # راجع نفس الملحوظة في store/views._base_products_queryset: 'units__discounts'
        # عشان سعر ما بعد الخصم في كارت المنتج ميعملش استعلام لكل صنف.
        .prefetch_related('units__discounts')
        .order_by('-new_arrival_at')
    )
