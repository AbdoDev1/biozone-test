"""
بناء ملفات Excel: تصدير الأصناف الحالية، وقالب فارغ للاستيراد. الاتنين
بنفس أعمدة parsing.py بالظبط عشان أي ملف بيتصدّر يفضل قابل للاستيراد
تاني من غير أي تعديل يدوي على الأعمدة.
"""
import openpyxl

from accounts.models import AccountType

from .common import discount_col_name

__all__ = [
    'build_products_export_workbook',
    'build_import_template_workbook',
]


def build_products_export_workbook(products):
    """
    بتبني ملف إكسل بنفس أعمدة قالب الاستيراد (صف لكل وحدة) لأي مجموعة
    أصناف (كل الأصناف، أو مجموعة مُنتقاة بالبحث/القسم) — مستخدمة في
    export_products (تصدير الكل) وexport_products_selected (تصدير المحدد).
    عمود code معبّى بكود كل صنف وأعمدة discount:<فئة> معبّية بنسبة الخصم
    الحالية لكل نوع حساب، عشان لو رفعت الملف تاني بعد التعديل، النظام
    يتعرّف على كل صنف بكوده ويحدّثه بدل ما يضيفه كصنف جديد. عمود quantity
    بيتصدّر دايمًا صفر (كمية "وارد" هتتضاف فوق الرصيد الحالي، مش الرصيد نفسه).
    """
    account_types = list(AccountType.objects.all().order_by('name'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'المنتجات'
    headers = [
        'code', 'barcode', 'category_slug', 'name_ar', 'unit_name',
        'qty_in_small', 'unit_price', 'quantity',
    ] + [discount_col_name(at) for at in account_types]
    ws.append(headers)

    for product in products:
        units = list(product.units.all())
        small = next((u for u in units if u.size == 'S'), None)
        large = next((u for u in units if u.size == 'L'), None)
        discount_unit = small or large
        discount_by_pk = {}
        if discount_unit:
            discount_by_pk = {d.account_type_id: d.discount_percent for d in discount_unit.discounts.all()}
        discount_cells = [
            float(discount_by_pk[at.pk]) if at.pk in discount_by_pk else '' for at in account_types
        ]
        blank_discounts = ['' for _ in account_types]

        if small:
            ws.append([
                product.code, product.barcode or '', product.category.slug, product.name_ar, small.name,
                1, float(small.unit_price), 0,
            ] + discount_cells)
        if large:
            ws.append([
                product.code, product.barcode or '', product.category.slug, product.name_ar, large.name,
                large.qty_in_small, float(large.unit_price), 0,
            ] + (blank_discounts if small else discount_cells))

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 20
    return wb


def build_import_template_workbook():
    """قالب فارغ (بأمثلة توضيحية) لأعمدة الاستيراد — نفس أعمدة التصدير بالظبط."""
    account_types = list(AccountType.objects.all().order_by('name'))
    discount_headers = [discount_col_name(at) for at in account_types]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'المنتجات'
    headers = [
        'code', 'barcode', 'category_slug', 'name_ar', 'unit_name',
        'qty_in_small', 'unit_price', 'quantity',
    ] + discount_headers
    ws.append(headers)

    blank_discounts = ['' for _ in account_types]
    small_discounts = [10 for _ in account_types]  # مثال: 10% لكل الفئات على القطعة
    large_discounts = [15 for _ in account_types]  # مثال: صنف بوحدة واحدة (كبرى بس)

    # مثال 1: صنف بوحدتين — الخصم بيتكتب على صف الوحدة الصغرى بس (قطعة)،
    # وصف الكرتونة بيتسيب فاضي لأن سعرها بيتحسب تلقائيًا من نسبة القطعة.
    # الباركود (اختياري) بيتكتب في صف واحد بس من صفوف نفس الصنف (بيتلمّ
    # تلقائيًا للصنف كله عند القراءة، زي category_slug بالظبط).
    ws.append(['', '', 'gauze', 'شاش طبي', 'قطعة', 1, 2.00, 200] + small_discounts)
    ws.append(['', '', 'gauze', 'شاش طبي', 'كرتونة', 50, 100.00, 0] + blank_discounts)

    # مثال 2: صنف بوحدة واحدة بس (كبرى) — الخصم بيتكتب على صفها هي نفسها.
    ws.append(['', '', 'gloves', 'قفازات لاتكس', 'كرتونة', 10, 250.00, 100] + large_discounts)

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 20
    return wb
