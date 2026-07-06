"""
حساب سعر الوحدة الصغرى (القطعة) تلقائيًا من سعر وكمية الوحدة الكبرى
(الكرتونة)، لو الموظف سايب حقل سعر القطعة فاضي.

القاعدة: سعر القطعة = سعر الكرتونة ÷ عدد القطع في الكرتونة (qty_in_small
بتاع الوحدة الكبرى). ده بيتطبّق على مستوى الـ POST data (قبل ما توصل
لأي ModelForm/Formset)، عشان نتجنّب تعقيد ترتيب الـ validation جوه
Django (الموديل بيرفض الحفظ لو الحقل فاضي حتى لو الفورمست بعدين هيحاول
يصلحه، لأن instance.full_clean() بيتنفذ لكل فورم على حدة قبل ما نوصل
لـ formset.clean()).

الدالة دي بتشتغل على أي POST data فيها فورمست بادئته `units` (زي
ProductUnitFormSet)، وبترجع نسخة معدّلة (QueryDict قابلة للتعديل) بدون
ما تلمس البيانات الأصلية.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def _to_decimal(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def autofill_small_unit_price(post_data, prefix='units'):
    """
    بترجع نسخة قابلة للتعديل من post_data، بعد ما تحط سعر الوحدة الصغرى
    (لو فاضي أو صفر) = سعر الوحدة الكبرى ÷ الكمية في الوحدة الصغرى
    (qty_in_small بتاع الكبرى نفسها). لو أي بيانات ناقصة أو غير صالحة،
    بترجع البيانات زي ما هي من غير أي تعديل (والـ validation العادي
    هيتكفل بإظهار رسالة الخطأ المناسبة).
    """
    data = post_data.copy()  # QueryDict.copy() بترجع نسخة mutable

    try:
        total_forms = int(data.get(f'{prefix}-TOTAL_FORMS', 0))
    except (TypeError, ValueError):
        return data

    large_price = None
    large_qty = None
    small_index = None
    small_price_raw = None

    for i in range(total_forms):
        if data.get(f'{prefix}-{i}-DELETE'):
            continue
        size = data.get(f'{prefix}-{i}-size')
        if size == 'L':
            large_price = _to_decimal(data.get(f'{prefix}-{i}-unit_price'))
            large_qty = _to_decimal(data.get(f'{prefix}-{i}-qty_in_small'))
        elif size == 'S':
            small_index = i
            small_price_raw = data.get(f'{prefix}-{i}-unit_price')

    if small_index is None:
        return data

    small_price = _to_decimal(small_price_raw)
    price_missing = small_price is None or small_price == 0

    if price_missing and large_price and large_qty and large_qty > 0:
        computed = (large_price / large_qty).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        data[f'{prefix}-{small_index}-unit_price'] = str(computed)

    return data
