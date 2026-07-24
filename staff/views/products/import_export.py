"""
استيراد/تصدير المنتجات من وإلى ملفات إكسل. منطق CRUD الأساسي (عرض/إضافة/
تعديل/حذف) منفصل في crud.py — راجع staff/views/products/__init__.py
للتوثيق الكامل لسبب الفصل.

منطق القراءة/التصنيف/الحفظ نفسه (parsing, fuzzy matching, commit) منقول
لـ products.services.import_export عشان يبقى قابل للاختبار من غير ما نمر
بـ request/session — هنا بس تنسيق الـ HTTP request/response وrenders.
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction

from products.models import Category, Product
from products.new_arrivals import NEW_ARRIVALS_WINDOW_DAYS
from products.services import import_export as import_export_service
from staff.permissions import perm_required
from staff.excel_utils import workbook_response

IMPORT_SESSION_KEY = 'product_import_batch'
# حماية من ملف إكسل ضخم بالغلط (أو مقصود): الدفعة بالكامل بتتخزن مؤقتًا في
# الـ session (قاعدة البيانات) بين شاشة المراجعة وشاشة التأكيد، فملف بعشرات
# الآلاف من الصفوف كان بيعمل صف session ضخم ويشغل الـ worker وقت طويل في
# طلب واحد. الحدين دول سقف منطقي لأي استيراد حقيقي (لو المخزن عنده كتالوج
# أكبر فعلاً، يقسّم الملف على أكتر من دفعة).
IMPORT_MAX_FILE_SIZE_MB = 5
IMPORT_MAX_ROWS = 3000

# Backward-compat: بعض الكود القديم (أو أي كود خارجي) كان بيستورد الثوابت
# دي من هنا مباشرة قبل الفصل — بتفضل متاحة كـ alias للمصدر الحقيقي.
FUZZY_MATCH_THRESHOLD = import_export_service.FUZZY_MATCH_THRESHOLD
DISCOUNT_COL_PREFIX = import_export_service.DISCOUNT_COL_PREFIX


@perm_required('products.add_product')
def import_products(request):
    """
    المرحلة الأولى: قراءة الملف وتصنيف كل صف (تحديث أكيد / إضافة جديدة
    أكيدة / يحتاج مراجعة) من غير أي حفظ فعلي، ثم عرض شاشة مراجعة. الحفظ
    الفعلي بيحصل بس في import_products_confirm بعد موافقة الموظف على أي
    صف يحتاج قرار بشري (اسم قريب من صنف موجود).
    """
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, 'يرجى اختيار ملف Excel أولاً.')
            return redirect('staff:import_products')
        if not excel_file.name.endswith('.xlsx'):
            messages.error(request, 'يجب أن يكون الملف بصيغة .xlsx')
            return redirect('staff:import_products')
        if excel_file.size > IMPORT_MAX_FILE_SIZE_MB * 1024 * 1024:
            messages.error(
                request,
                f'حجم الملف أكبر من الحد المسموح ({IMPORT_MAX_FILE_SIZE_MB} ميجا). '
                f'يرجى تقسيم الملف على أكتر من دفعة استيراد.'
            )
            return redirect('staff:import_products')

        rows, errors, error_message = import_export_service.read_import_workbook(
            excel_file, max_rows=IMPORT_MAX_ROWS,
        )
        if error_message:
            messages.error(request, error_message)
            return redirect('staff:import_products')

        if not rows:
            messages.error(request, 'مفيش أي صف صالح في الملف.')
            for err in errors:
                messages.warning(request, err)
            return redirect('staff:import_products')

        request.session[IMPORT_SESSION_KEY] = {'rows': rows, 'errors': errors}
        return redirect('staff:import_products_review')
    return render(request, 'staff/products/import.html')


@perm_required('products.add_product')
def import_products_review(request):
    """
    شاشة المراجعة: بتعرض عدد الأصناف اللي هتتحدّث/هتتضاف بثقة تلقائيًا،
    وبتوقف عند أي صف اسمه قريب من صنف موجود وتسأل الموظف صراحةً هل ده
    نفس الصنف (تحديث) ولا صنف جديد فعلًا — قبل أي حفظ في قاعدة البيانات.
    """
    batch = request.session.get(IMPORT_SESSION_KEY)
    if not batch:
        messages.error(request, 'مفيش عملية استيراد جارية. من فضلك ارفع الملف تاني.')
        return redirect('staff:import_products')

    rows = batch['rows']
    context = {
        'errors': batch['errors'],
        'update_rows': [r for r in rows if r['action'] == 'update'],
        'create_rows': [r for r in rows if r['action'] == 'create'],
        'review_rows': [r for r in rows if r['action'] == 'review'],
        'new_arrivals_window_days': NEW_ARRIVALS_WINDOW_DAYS,
    }
    return render(request, 'staff/products/import_review.html', context)


@perm_required('products.add_product')
def import_products_confirm(request):
    """
    المرحلة التانية: بتاخد قرارات الموظف على صفوف "المراجعة" (اتحدد لكل
    واحد منها إما تحديث صنف بعينه أو إضافته كصنف جديد فعلًا) وتنفّذ الحفظ
    الفعلي لكل صفوف الدفعة مرة واحدة داخل transaction واحدة.
    """
    if request.method != 'POST':
        return redirect('staff:import_products')

    batch = request.session.get(IMPORT_SESSION_KEY)
    if not batch:
        messages.error(request, 'انتهت صلاحية عملية الاستيراد دي. من فضلك ارفع الملف تاني.')
        return redirect('staff:import_products')

    rows = batch['rows']
    decisions = {
        row['row_num']: request.POST.get(f"decision_{row['row_num']}", 'new')
        for row in rows if row['action'] == 'review'
    }
    try:
        with transaction.atomic():
            created_count, updated_count, restocked_count = import_export_service.commit_import_batch(
                rows, decisions, request.user,
            )
    except Exception as e:
        messages.error(request, f'حصل خطأ أثناء الحفظ ولم يتم حفظ أي صنف: {str(e)}')
        return redirect('staff:import_products')

    del request.session[IMPORT_SESSION_KEY]
    if created_count:
        messages.success(request, f'تم إضافة {created_count} صنف جديد.')
    if updated_count:
        messages.success(request, f'تم تحديث {updated_count} صنف موجود.')
    for err in batch['errors']:
        messages.warning(request, err)

    # إشعار العملاء بالوارد الجديد — اختياري، الموظف بيحدده من شاشة المراجعة.
    # new_arrival_at اتحدّث تلقائيًا لكل صنف جديد أو اتزوّد رصيده (راجع
    # Product.save و StockMovement.save)، فمفيش داعي نحسب حاجة تانية هنا —
    # بس نتأكد إن فيه فعلاً حاجة جديدة تستاهل إشعار قبل ما نبعته.
    new_arrivals_total = created_count + restocked_count
    if request.POST.get('notify_clients') == 'on' and new_arrivals_total > 0:
        from notifications.services import notify_all_clients
        notify_all_clients(
            kind='NEW_ARRIVALS',
            title='وارد جديد في المتجر 🆕',
            message=f'تم إضافة {new_arrivals_total} صنف جديد أو تزويد رصيده — اطّلع على صفحة الوارد.',
            url_name='store:new_arrivals',
        )
        messages.success(request, 'تم إرسال إشعار الوارد الجديد لكل العملاء.')

    return redirect('staff:product_list')


@perm_required('products.view_product')
def download_template(request):
    """
    قالب فيه صف لكل وحدة (مش صف لكل صنف) — راجع
    products.services.import_export.build_import_template_workbook لتفاصيل الصيغة.
    """
    wb = import_export_service.build_import_template_workbook()
    return workbook_response(wb, 'biozone_products_template.xlsx')


@perm_required('products.view_product')
def export_products(request):
    """تصدير كل الأصناف الحالية دفعة واحدة (بدون اختيار)."""
    products = Product.objects.select_related('category').prefetch_related(
        'units__discounts__account_type',
    ).all()
    wb = import_export_service.build_products_export_workbook(products)
    return workbook_response(wb, 'biozone_products_export.xlsx')


@perm_required('products.view_product')
def export_products_select(request):
    """
    صفحة اختيار الأصناف قبل التصدير: تقدر تبحث وتحدد أصناف بعينها، أو
    تحدد قسم كامل (وبعدين تشيل منه أي صنف مش عايزه)، والنظام هيصدّر بس
    اللي محدد فعليًا لملف إكسل بنفس صيغة "تصدير الأصناف الحالية".
    """
    categories = Category.objects.filter(is_active=True).order_by('name')
    products = Product.objects.select_related('category').order_by('name_ar')
    products_data = [
        {
            'id': p.pk,
            'name': p.name_ar,
            'code': p.code,
            'category_slug': p.category.slug,
            'category_name': p.category.name,
        }
        for p in products
    ]
    return render(request, 'staff/products/export_select.html', {
        'categories': categories,
        'products_json': products_data,
    })


@perm_required('products.view_product')
def export_products_selected(request):
    """يستقبل قائمة IDs من صفحة الاختيار ويصدّرها كملف إكسل واحد."""
    if request.method != 'POST':
        return redirect('staff:export_products_select')

    ids = [pk for pk in request.POST.getlist('product_ids') if pk.isdigit()]
    if not ids:
        messages.warning(request, 'لازم تحدد صنف واحد على الأقل قبل التصدير.')
        return redirect('staff:export_products_select')

    products = Product.objects.select_related('category').prefetch_related(
        'units__discounts__account_type',
    ).filter(pk__in=ids)
    wb = import_export_service.build_products_export_workbook(products)
    return workbook_response(wb, 'biozone_products_export_selected.xlsx')
