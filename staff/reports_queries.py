"""
منطق الاستعلامات والتجميع لقسم التقارير (staff/views/reports.py).

المصدر الأساسي لكل تقارير المبيعات/الربح هنا هو orders.OrderItem بس مقصور
على الطلبات المُسلَّمة (Order.Status.DELIVERED) واللي ليها فاتورة فعلاً —
دي أصناف مبيعات حقيقية فعلية (مش مجرد طلب في السلة لسه ماتاكدش)، ومحتفظة
بكل الـ FK اللازمة للفلترة (المنتج، القسم، العميل) ولحساب الربح
(product_unit.cost_price) بعكس invoices.InvoiceItem اللي بياخد Snapshot
نصّي بس (product_name كنص) بدون FK حقيقي نقدر نفلتر أو نجمّع بيه.

تاريخ البيع المعتمد في كل الفلاتر = invoice.issued_at (لحظة تسليم الطلب
الفعلية وإصدار فاتورته) — أدق من order.created_at لأن الطلب ممكن يفضل فترة
طويلة PENDING/NEEDS_APPROVAL قبل ما يتسلّم فعليًا.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Sum, Count, F, DecimalField, ExpressionWrapper, Q, Avg,
)
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import User, Employee
from orders.models import Order, OrderItem
from products.models import Product, Category
from inventory.models import Inventory

MONEY = DecimalField(max_digits=14, decimal_places=2)

# ---------------------------------------------------------------------
# فترات جاهزة لشريط الفلاتر الموحّد
# ---------------------------------------------------------------------
PERIOD_CHOICES = [
    ('today', 'اليوم'),
    ('week', 'آخر 7 أيام'),
    ('month', 'الشهر الحالي'),
    ('year', 'السنة الحالية'),
    ('custom', 'فترة مخصصة'),
    ('all', 'كل الفترات'),
]


def resolve_period(request):
    """
    بترجع (start, end, period_key) حسب اختيار المستخدم في شريط الفلاتر.
    start/end هما datetime واعية بالـ timezone (أو None لو 'all' أو لو
    الفترة المخصصة ناقصة تاريخ). end دايمًا نهاية اليوم المحدد (23:59:59)
    عشان يشمل مبيعات اليوم ده بالكامل.
    """
    now = timezone.localtime()
    period = request.GET.get('period', 'month')
    start = end = None

    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == 'week':
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == 'year':
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == 'custom':
        from_str = request.GET.get('date_from', '').strip()
        to_str = request.GET.get('date_to', '').strip()
        import datetime as _dt
        if from_str:
            try:
                d = _dt.datetime.strptime(from_str, '%Y-%m-%d')
                start = timezone.make_aware(d.replace(hour=0, minute=0, second=0))
            except ValueError:
                start = None
        if to_str:
            try:
                d = _dt.datetime.strptime(to_str, '%Y-%m-%d')
                end = timezone.make_aware(d.replace(hour=23, minute=59, second=59))
            except ValueError:
                end = None
        else:
            end = now
    elif period == 'all':
        start = end = None
    else:
        period = 'month'
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now

    return start, end, period


class ReportFilters:
    """
    يقرأ شريط الفلاتر الموحّد من request.GET ويجهّز كل حاجة محتاجينها:
    الفترة الزمنية، الموظف (اللي سلّم/أصدر الفاتورة)، العميل، المنتج، القسم.
    """

    def __init__(self, request):
        self.request = request
        self.start, self.end, self.period = resolve_period(request)
        self.employee_id = request.GET.get('employee', '').strip()
        self.client_id = request.GET.get('client', '').strip()
        self.product_id = request.GET.get('product', '').strip()
        self.category_id = request.GET.get('category', '').strip()
        self.date_from = request.GET.get('date_from', '').strip()
        self.date_to = request.GET.get('date_to', '').strip()

    def base_order_items(self):
        """كل أصناف الطلبات المُسلَّمة (مبيعات فعلية) بعد تطبيق كل الفلاتر."""
        qs = OrderItem.objects.filter(
            order__status=Order.Status.DELIVERED,
            order__invoice__isnull=False,
        ).select_related(
            'order', 'order__client', 'order__client__client_profile',
            'order__invoice', 'order__invoice__issued_by',
            'product_unit', 'product_unit__product', 'product_unit__product__category',
        )
        if self.start:
            qs = qs.filter(order__invoice__issued_at__gte=self.start)
        if self.end:
            qs = qs.filter(order__invoice__issued_at__lte=self.end)
        if self.employee_id:
            qs = qs.filter(order__invoice__issued_by_id=self.employee_id)
        if self.client_id:
            qs = qs.filter(order__client_id=self.client_id)
        if self.product_id:
            qs = qs.filter(product_unit__product_id=self.product_id)
        if self.category_id:
            qs = qs.filter(product_unit__product__category_id=self.category_id)
        return qs

    def base_invoices(self):
        """الفواتير (مستوى الفاتورة/الطلب ككل) بعد تطبيق نفس الفلاتر — للمبيعات على مستوى الفاتورة."""
        from invoices.models import Invoice
        qs = Invoice.objects.select_related('order', 'order__client', 'issued_by')
        if self.start:
            qs = qs.filter(issued_at__gte=self.start)
        if self.end:
            qs = qs.filter(issued_at__lte=self.end)
        if self.employee_id:
            qs = qs.filter(issued_by_id=self.employee_id)
        if self.client_id:
            qs = qs.filter(order__client_id=self.client_id)
        if self.product_id or self.category_id:
            item_qs = self.base_order_items()
            order_ids = item_qs.values_list('order_id', flat=True).distinct()
            qs = qs.filter(order_id__in=order_ids)
        return qs

    def filter_context(self):
        """قوائم اختيار شريط الفلاتر (موظفين، عملاء، منتجات، أقسام) + القيم المختارة حاليًا."""
        return {
            'employees': Employee.objects.all().order_by('username'),
            'clients': User.objects.filter(role=User.Role.CLIENT, client_profile__isnull=False)
                .select_related('client_profile').order_by('client_profile__business_name'),
            'categories': Category.objects.filter(is_active=True).order_by('name'),
            'products': Product.objects.filter(is_active=True).order_by('name_ar').only('id', 'name_ar', 'name_en'),
            'period_choices': PERIOD_CHOICES,
            'selected_period': self.period,
            'selected_employee': self.employee_id,
            'selected_client': self.client_id,
            'selected_product': self.product_id,
            'selected_category': self.category_id,
            'date_from': self.date_from,
            'date_to': self.date_to,
        }


def item_annotations(qs):
    """يضيف مجاميع الإيراد/التكلفة/الربح لكل صف مُجمَّع (annotate) من OrderItem."""
    revenue_expr = ExpressionWrapper(F('unit_price') * F('quantity'), output_field=MONEY)
    cost_expr = ExpressionWrapper(F('product_unit__cost_price') * F('quantity'), output_field=MONEY)
    return qs.annotate(_revenue=revenue_expr, _cost=cost_expr)


def totals_for_items(qs):
    """إجماليات عامة (إيراد/تكلفة/ربح/عدد قطع) لمجموعة أصناف مبيعات."""
    qs = item_annotations(qs)
    agg = qs.aggregate(
        revenue=Sum('_revenue'),
        cost=Sum('_cost'),
        qty=Sum('quantity'),
    )
    revenue = agg['revenue'] or Decimal('0')
    cost = agg['cost'] or Decimal('0')
    return {
        'revenue': revenue,
        'cost': cost,
        'profit': revenue - cost,
        'qty': agg['qty'] or 0,
        'margin_percent': (((revenue - cost) / revenue) * 100) if revenue else Decimal('0'),
    }


def sales_summary(invoice_qs):
    """ملخص المبيعات على مستوى الفاتورة: عدد الفواتير، الإجمالي، متوسط الفاتورة."""
    agg = invoice_qs.aggregate(count=Count('id'), total=Sum('total'))
    count = agg['count'] or 0
    total = agg['total'] or Decimal('0')
    avg = (total / count) if count else Decimal('0')
    return {'count': count, 'total': total, 'avg': avg}


def products_sold_report(item_qs, order_by='revenue'):
    """
    تجميع أصناف المبيعات حسب المنتج: الكمية، الإيراد، التكلفة، الربح، ونسبة
    مساهمته في إجمالي المبيعات المفلترة.
    order_by: 'revenue' | 'qty' | 'profit'
    """
    qs = item_annotations(item_qs).values(
        'product_unit__product_id',
        'product_unit__product__name_ar',
        'product_unit__product__name_en',
        'product_unit__product__code',
        'product_unit__product__category__name',
    ).annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('_revenue'),
        total_cost=Sum('_cost'),
    ).annotate(
        total_profit=ExpressionWrapper(F('total_revenue') - F('total_cost'), output_field=MONEY),
    )

    order_map = {
        'revenue': '-total_revenue',
        'qty': '-total_qty',
        'profit': '-total_profit',
    }
    qs = qs.order_by(order_map.get(order_by, '-total_revenue'))

    rows = list(qs)
    grand_total_revenue = sum((r['total_revenue'] or Decimal('0')) for r in rows) or Decimal('0')
    for r in rows:
        r['display_name'] = r['product_unit__product__name_en'] or r['product_unit__product__name_ar']
        r['share_percent'] = (
            (r['total_revenue'] / grand_total_revenue * 100) if grand_total_revenue else Decimal('0')
        )
    return rows


def top_customers_report(item_qs):
    """تجميع المبيعات حسب العميل: إجمالي المشتريات، عدد الفواتير، متوسط الفاتورة، آخر عملية شراء."""
    from django.db.models import Max
    from invoices.models import Invoice

    qs = item_annotations(item_qs).values(
        'order__client_id',
        'order__client__client_profile__business_name',
        'order__client__username',
    ).annotate(
        total_revenue=Sum('_revenue'),
        invoices_count=Count('order_id', distinct=True),
    ).order_by('-total_revenue')

    rows = list(qs)
    client_ids = [r['order__client_id'] for r in rows]
    last_purchase_map = dict(
        Invoice.objects.filter(order__client_id__in=client_ids)
        .values('order__client_id')
        .annotate(last=Max('issued_at'))
        .values_list('order__client_id', 'last')
    )
    for r in rows:
        r['display_name'] = r['order__client__client_profile__business_name'] or r['order__client__username']
        r['avg_invoice'] = (r['total_revenue'] / r['invoices_count']) if r['invoices_count'] else Decimal('0')
        r['last_purchase'] = last_purchase_map.get(r['order__client_id'])
    return rows


def stagnant_products_report(days=30, category_id=None, product_id=None):
    """
    منتجات لم تُبع (لا يوجد أي OrderItem ضمن طلب مُسلَّم) منذ 'days' يومًا،
    أو لم تُبع إطلاقًا. بيرجع فقط المنتجات النشطة اللي ليها رصيد مخزون.
    """
    cutoff = timezone.now() - timedelta(days=days)

    recently_sold_ids = OrderItem.objects.filter(
        order__status=Order.Status.DELIVERED,
        order__invoice__isnull=False,
        order__invoice__issued_at__gte=cutoff,
    ).values_list('product_unit__product_id', flat=True).distinct()

    qs = Inventory.objects.select_related('product', 'product__category').filter(
        product__is_active=True,
    ).exclude(product_id__in=list(recently_sold_ids))

    if category_id:
        qs = qs.filter(product__category_id=category_id)
    if product_id:
        qs = qs.filter(product_id=product_id)

    # آخر تاريخ بيع فعلي (لو موجود) لكل منتج راكد — لعرضه في الجدول.
    from django.db.models import Max
    last_sale_map = dict(
        OrderItem.objects.filter(
            order__status=Order.Status.DELIVERED,
            order__invoice__isnull=False,
        ).values('product_unit__product_id')
        .annotate(last=Max('order__invoice__issued_at'))
        .values_list('product_unit__product_id', 'last')
    )

    rows = []
    for inv in qs.order_by('-quantity'):
        rows.append({
            'inventory': inv,
            'product': inv.product,
            'last_sale': last_sale_map.get(inv.product_id),
        })
    return rows


def daily_sales_for_dashboard(days=30):
    """
    آخر N يوم من المبيعات (على مستوى الفاتورة) — سلسلة زمنية بسيطة لرسم بياني.
    بيرجع list of {'date': date, 'total': Decimal}.
    """
    from invoices.models import Invoice
    since = timezone.now() - timedelta(days=days)
    rows = (
        Invoice.objects.filter(issued_at__gte=since)
        .annotate(day=TruncDate('issued_at'))
        .values('day')
        .annotate(total=Sum('total'), count=Count('id'))
        .order_by('day')
    )
    by_day = {r['day']: r for r in rows}
    today = timezone.localtime().date()
    series = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        r = by_day.get(d)
        series.append({'date': d, 'total': (r['total'] if r else Decimal('0')), 'count': (r['count'] if r else 0)})
    return series


def monthly_profit_series(months=6):
    """آخر N شهر: إيراد/تكلفة/ربح لكل شهر — لرسم بياني الأرباح الشهرية في لوحة المؤشرات."""
    now = timezone.localtime()
    series = []
    for i in range(months - 1, -1, -1):
        # نحسب أول يوم في الشهر i شهر قبل الحالي، وأول يوم في الشهر اللي بعده كحد أقصى.
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        start = timezone.make_aware(timezone.datetime(year, month, 1))
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
        end = timezone.make_aware(timezone.datetime(next_year, next_month, 1))

        item_qs = OrderItem.objects.filter(
            order__status=Order.Status.DELIVERED,
            order__invoice__isnull=False,
            order__invoice__issued_at__gte=start,
            order__invoice__issued_at__lt=end,
        )
        totals = totals_for_items(item_qs)
        series.append({
            'label': start.strftime('%Y-%m'),
            'revenue': totals['revenue'],
            'cost': totals['cost'],
            'profit': totals['profit'],
        })
    return series
