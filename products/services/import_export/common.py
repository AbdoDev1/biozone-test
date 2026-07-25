"""
ثوابت وأدوات مشتركة بين مرحلتي القراءة (parsing.py) والتصدير (export.py) —
الاتنين محتاجين نفس تسمية أعمدة الخصم ونفس ترتيب الأعمدة المطلوبة، عشان
ملف بيتصدّر من النظام يفضل قابل للاستيراد تاني بنفس الصيغة بالظبط.
"""

from django.utils.text import slugify

FUZZY_MATCH_THRESHOLD = 0.82  # 82% تشابه فأكثر = "محتاج مراجعة بشرية"

# عمود الخصم لكل نوع حساب (فئة) بيتسمى discount:<اسم نوع الحساب> — الأنواع
# نفسها ديناميكية (بتتضاف/تتحذف من شاشة "أنواع الحسابات")، فمفيش عدد أعمدة
# ثابت: القالب/التصدير بيولّد عمود لكل نوع موجود وقت التحميل، والاستيراد
# بيدوّر على أي عمود بادئته discount: ويطابقه بالاسم مع الأنواع الحالية —
# لو النوع اتحذف أو الاسم اتغيّر، العمود بيتجاهل بدل ما يفشل الاستيراد كله.
DISCOUNT_COL_PREFIX = 'discount:'

REQUIRED_IMPORT_HEADERS = ['name_ar', 'unit_name', 'qty_in_small', 'unit_price']


def discount_col_name(account_type):
    return f'{DISCOUNT_COL_PREFIX}{account_type.name}'


def resolve_category(value):
    """
    بتدوّر على القسم من قيمة عمود category_slug في ملف الإكسل — بتقبل إما
    الـslug الحقيقي (زي "عناية-بالاسنان") أو اسم القسم العادي بمسافات
    عادية (زي "عناية بالاسنان")، عشان الموظف اللي بيجهّز الملف مضطرش
    يعرف صيغة الـslug بالظبط (شرطات بدل مسافات، همزات المطابقة...).

    الترتيب: تطابق تام مع slug موجود، وإلا تطابق تام مع name موجود، وإلا
    نحوّل القيمة نفسها لـslug (بنفس دالة توليد الـslug الأصلية) ونجرّب
    تاني — بيغطي حالة "القيمة فيها مسافات بس لو تحوّلت لslug هتطابق قسم
    موجود". بيرجّع الـCategory أو None لو مفيش تطابق بأي طريقة.
    """
    from products.models import Category

    value = (value or '').strip()
    if not value:
        return None

    category = Category.objects.filter(slug=value).first()
    if category:
        return category

    category = Category.objects.filter(name=value).first()
    if category:
        return category

    normalized_slug = slugify(value, allow_unicode=True)
    if normalized_slug and normalized_slug != value:
        category = Category.objects.filter(slug=normalized_slug).first()
        if category:
            return category

    return None


import re

_ROW_PREFIX_RE = re.compile(r'^سطر (\d+): (.*)$')


def group_import_errors(errors):
    """
    ملف فيه صف واحد فيه مشكلة (زي عمود ناقص أو قيمة غلط) بيرجّع نفس رسالة
    الخطأ مكررة لكل صف من نفس النوع — لو الملف فيه 1000 صف وكلهم ناقصين
    نفس العمود مثلاً، كان بيطلع 1000 سطر خطأ منفصل (في الصفحة وبعدين كـ
    1000 toast منفصل بعد الحفظ). هنا بنجمّع الرسائل المتطابقة (بعد ما نشيل
    رقم السطر بس) في مجموعة واحدة ومعاها كل أرقام السطور المتأثرة.

    بيرجّع list من dicts: {'message': النص العام, 'row_nums': [...], 'count': N}
    مرتبة الأكتر تكرارًا الأول. الرسائل اللي مش بصيغة "سطر N: ..." (زي أخطاء
    عامة عن الملف كله) بتتحط كل واحدة لوحدها زي ما هي.
    """
    groups = {}
    order = []
    for err in errors:
        m = _ROW_PREFIX_RE.match(err)
        if m:
            row_num, message = int(m.group(1)), m.group(2)
        else:
            row_num, message = None, err
        if message not in groups:
            groups[message] = []
            order.append(message)
        if row_num is not None:
            groups[message].append(row_num)

    result = [
        {'message': message, 'row_nums': groups[message], 'count': len(groups[message]) or 1}
        for message in order
    ]
    result.sort(key=lambda g: g['count'], reverse=True)
    return result
