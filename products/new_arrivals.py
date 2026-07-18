"""
"الوارد الجديد" — منتجات اتضافت لأول مرة أو اتزوّد رصيدها، ولسه رصيدها
الحالي فوق الحد الأدنى (Inventory.min_quantity). الاختيار التصميمي هنا
مقصود: مفيش موديل أو جدول منفصل لـ"الوارد"، ومفيش نسخ مكرّرة من بيانات
المنتج — هي نفس صفوف Product بالظبط. "الوارد" مجرد View مفلترة، والصنف
بيرجع مكانه في المتجر العادي (ومش بيتكرر) أول ما أي شرط من الاتنين يتحقق:

1) الكمية: الرصيد (Inventory.quantity) وصل الحد الأدنى المحدد للصنف —
   يعني اتهلك بما يكفي إنه مابقاش "زيادة عن اللزوم" في السوق.
2) الوقت: NEW_ARRIVALS_WINDOW_DAYS يوم عدّوا من new_arrival_at — شبكة
   أمان عشان صنف بطيء الحركة (رصيده مانزلش) ميفضلش عالق في الوارد
   للأبد لو محدش اشتراه.

الفايدة: مصدر حقيقة واحد (source of truth واحد)، صفر تكلفة صيانة
إضافية، وبتتوسّع عادي (فلتر على حقول مفهرسة/مربوطة) حتى لو الكتالوج كبر.
"""
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from .models import Product

NEW_ARRIVALS_WINDOW_DAYS = 7


def new_arrivals_queryset():
    """
    كل المنتجات النشطة اللي:
    - new_arrival_at بتاعها خلال آخر NEW_ARRIVALS_WINDOW_DAYS يوم (لسه ماعداش السقف الزمني)
    - ورصيدها الحالي لسه أكبر من الحد الأدنى (لسه مايتهلكش بما يكفي)

    منتج من غير سجل مخزون (Inventory) أصلاً معندوش رصيد يتقاس، فبيتستبعد
    تلقائيًا (inner join عادي بيرجع بس المنتجات اللي ليها Inventory).
    """
    cutoff = timezone.now() - timedelta(days=NEW_ARRIVALS_WINDOW_DAYS)
    return (
        Product.objects.filter(
            is_active=True,
            new_arrival_at__gte=cutoff,
            inventory__quantity__gt=F('inventory__min_quantity'),
        )
        .select_related('category', 'inventory')
        .prefetch_related('units')
        .order_by('-new_arrival_at')
    )
