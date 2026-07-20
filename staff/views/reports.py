from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import F, Sum
from django.shortcuts import render
from django.utils import timezone

from inventory.models import Inventory
from orders.models import Order, OrderItem
from staff.permissions import perm_required
from staff.excel_utils import build_simple_workbook, workbook_response
from staff import reports_queries as rq

STAFF_LIST_PAGE_SIZE = 50


# =====================================================================
# 1) لوحة المؤشرات (Executive Dashboard)
# =====================================================================
@perm_required('staff.view_reports')
def dashboard(request):
    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    from invoices.models import Invoice
    from accounts.models import ClientProfile

    today_summary = rq.sales_summary(Invoice.objects.filter(issued_at__gte=today_start))
    month_summary = rq.sales_summary(Invoice.objects.filter(issued_at__gte=month_start))

    month_item_qs = OrderItem.objects.filter(
        order__status=Order.Status.DELIVERED,
        order__invoice__isnull=False,
        order__invoice__issued_at__gte=month_start,
    )
    month_profit = rq.totals_for_items(month_item_qs)

    inv_qs = Inventory.objects.select_related('product')
    low_stock_count = inv_qs.low_stock().count()

    total_customers = ClientProfile.objects.filter(user__status='ACTIVE').count()
    active_customers = ClientProfile.objects.filter(
        user__status='ACTIVE', user__orders__status=Order.Status.DELIVERED,
    ).distinct().count()

    # قيمة المخزون الحالية = رصيد كل صنف (بالقطعة) × سعر جمهور أصغر وحدة له.
    stock_value = Decimal('0')
    for inv in inv_qs.prefetch_related('product__units'):
        smallest = inv.product.smallest_unit
        if smallest:
            stock_value += Decimal(inv.quantity) * smallest.unit_price

    top_products = rq.products_sold_report(month_item_qs, order_by='revenue')[:5]
    top_customers = rq.top_customers_report(month_item_qs)[:5]

    context = {
        'today_summary': today_summary,
        'month_summary': month_summary,
        'month_profit': month_profit,
        'total_products': inv_qs.count(),
        'low_stock_count': low_stock_count,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'stock_value': stock_value,
        'top_products': top_products,
        'top_customers': top_customers,
        'daily_series': rq.daily_sales_for_dashboard(days=14),
        'monthly_series': rq.monthly_profit_series(months=6),
    }
    return render(request, 'staff/reports/dashboard.html', context)


# =====================================================================
# 2) تقرير المبيعات
# =====================================================================
@perm_required('staff.view_reports')
def sales_report(request):
    filters = rq.ReportFilters(request)
    invoice_qs = filters.base_invoices().order_by('-issued_at')
    summary = rq.sales_summary(invoice_qs)

    # الخصومات = الفرق بين سعر الجمهور والسعر الفعلي على كل صنف مبيع في نطاق الفلاتر.
    item_qs = filters.base_order_items()
    discount_total = item_qs.aggregate(
        d=Sum((F('public_price') - F('unit_price')) * F('quantity'))
    )['d'] or Decimal('0')

    if request.GET.get('export') == 'excel':
        return _export_sales_excel(invoice_qs)

    paginator = Paginator(invoice_qs, STAFF_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'invoices': page_obj,
        'page_obj': page_obj,
        'summary': summary,
        'discount_total': discount_total,
        'net_total': summary['total'] - discount_total,
    }
    context.update(filters.filter_context())
    return render(request, 'staff/reports/sales.html', context)


def _export_sales_excel(invoice_qs):
    data_rows = [
        [
            inv.invoice_number,
            timezone.localtime(inv.issued_at).strftime('%Y-%m-%d %H:%M'),
            inv.client_name,
            inv.issued_by.username if inv.issued_by else '—',
            float(inv.total),
        ]
        for inv in invoice_qs.select_related('order__client', 'issued_by')
    ]
    wb = build_simple_workbook(
        sheet_title='تقرير المبيعات',
        headers=['رقم الفاتورة', 'التاريخ', 'العميل', 'الموظف', 'الإجمالي (ج.م)'],
        rows=data_rows,
    )
    return workbook_response(wb, 'biozone_sales_report.xlsx')


# =====================================================================
# 3) تقرير المنتجات المباعة (يشمل "الأكثر مبيعًا" عبر خيار الترتيب)
# =====================================================================
@perm_required('staff.view_reports')
def products_sold(request):
    filters = rq.ReportFilters(request)
    item_qs = filters.base_order_items()
    sort = request.GET.get('sort', 'revenue')
    if sort not in ('revenue', 'qty', 'profit'):
        sort = 'revenue'
    rows = rq.products_sold_report(item_qs, order_by=sort)

    if request.GET.get('export') == 'excel':
        return _export_products_excel(rows)

    paginator = Paginator(rows, STAFF_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'rows': page_obj,
        'page_obj': page_obj,
        'sort': sort,
        'totals': rq.totals_for_items(item_qs),
    }
    context.update(filters.filter_context())
    return render(request, 'staff/reports/products.html', context)


def _export_products_excel(rows):
    data_rows = [
        [
            r['product_unit__product__code'],
            r['display_name'],
            r['product_unit__product__category__name'] or '—',
            r['total_qty'],
            float(r['total_revenue'] or 0),
            float(r['total_profit'] or 0),
            round(float(r['share_percent'] or 0), 2),
        ]
        for r in rows
    ]
    wb = build_simple_workbook(
        sheet_title='المنتجات المباعة',
        headers=['كود الصنف', 'اسم المنتج', 'القسم', 'الكمية المباعة', 'الإيراد (ج.م)', 'الربح (ج.م)', 'نسبة المساهمة %'],
        rows=data_rows,
    )
    return workbook_response(wb, 'biozone_products_sold.xlsx')


# =====================================================================
# 4) تقرير أفضل العملاء
# =====================================================================
@perm_required('staff.view_reports')
def top_customers(request):
    filters = rq.ReportFilters(request)
    item_qs = filters.base_order_items()
    rows = rq.top_customers_report(item_qs)

    if request.GET.get('export') == 'excel':
        return _export_customers_excel(rows)

    paginator = Paginator(rows, STAFF_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {'rows': page_obj, 'page_obj': page_obj}
    context.update(filters.filter_context())
    return render(request, 'staff/reports/customers.html', context)


def _export_customers_excel(rows):
    data_rows = [
        [
            r['display_name'],
            float(r['total_revenue'] or 0),
            r['invoices_count'],
            float(r['avg_invoice'] or 0),
            timezone.localtime(r['last_purchase']).strftime('%Y-%m-%d') if r['last_purchase'] else '—',
        ]
        for r in rows
    ]
    wb = build_simple_workbook(
        sheet_title='أفضل العملاء',
        headers=['العميل', 'إجمالي المشتريات (ج.م)', 'عدد الفواتير', 'متوسط الفاتورة (ج.م)', 'آخر عملية شراء'],
        rows=data_rows,
        column_width=24,
    )
    return workbook_response(wb, 'biozone_top_customers.xlsx')


# =====================================================================
# 5) تقرير الأرباح
# =====================================================================
@perm_required('staff.view_reports')
def profit_report(request):
    filters = rq.ReportFilters(request)
    item_qs = filters.base_order_items()
    totals = rq.totals_for_items(item_qs)
    monthly_series = rq.monthly_profit_series(months=12)

    if request.GET.get('export') == 'excel':
        return _export_profit_excel(monthly_series, totals)

    context = {'totals': totals, 'monthly_series': monthly_series}
    context.update(filters.filter_context())
    return render(request, 'staff/reports/profit.html', context)


def _export_profit_excel(monthly_series, totals):
    data_rows = [[m['label'], float(m['revenue']), float(m['cost']), float(m['profit'])] for m in monthly_series]
    data_rows.append(['', '', '', ''])
    data_rows.append(['الإجمالي (الفترة المختارة)', float(totals['revenue']), float(totals['cost']), float(totals['profit'])])
    wb = build_simple_workbook(
        sheet_title='تقرير الأرباح',
        headers=['الشهر', 'الإيرادات (ج.م)', 'تكلفة البضاعة (ج.م)', 'الربح الإجمالي (ج.م)'],
        rows=data_rows,
    )
    return workbook_response(wb, 'biozone_profit_report.xlsx')


# =====================================================================
# 6) تقرير المنتجات الراكدة
# =====================================================================
@perm_required('staff.view_reports')
def stagnant_products(request):
    days_custom = request.GET.get('days_custom', '').strip()
    days_preset = request.GET.get('days', '30').strip()
    raw = days_custom or days_preset
    try:
        days = int(raw)
    except ValueError:
        days = 30
    days = max(1, min(days, 3650))

    category_id = request.GET.get('category', '').strip() or None
    product_id = request.GET.get('product', '').strip() or None
    rows = rq.stagnant_products_report(days=days, category_id=category_id, product_id=product_id)

    if request.GET.get('export') == 'excel':
        return _export_stagnant_excel(rows)

    paginator = Paginator(rows, STAFF_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    from products.models import Category, Product
    context = {
        'rows': page_obj,
        'page_obj': page_obj,
        'days': days,
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'products': Product.objects.filter(is_active=True).order_by('name_ar').only('id', 'name_ar', 'name_en'),
        'selected_category': category_id or '',
        'selected_product': product_id or '',
    }
    return render(request, 'staff/reports/stagnant.html', context)


def _export_stagnant_excel(rows):
    data_rows = []
    for r in rows:
        product = r['product']
        data_rows.append([
            product.code,
            product.display_name,
            product.category.name if product.category_id else '—',
            r['inventory'].quantity_display,
            timezone.localtime(r['last_sale']).strftime('%Y-%m-%d') if r['last_sale'] else 'لم يُبع من قبل',
        ])
    wb = build_simple_workbook(
        sheet_title='منتجات راكدة',
        headers=['كود الصنف', 'اسم المنتج', 'القسم', 'الرصيد الحالي', 'آخر عملية بيع'],
        rows=data_rows,
        column_width=24,
    )
    return workbook_response(wb, 'biozone_stagnant_products.xlsx')
