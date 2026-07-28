# Data migration — حل مشكلة bidi الموثّقة في ROADMAP.md (قسم "قرار محسوم"):
# توكن مقاس لاتيني (S/M/L/XL/XXL/XXXL) كان بيتكتب كجزء من name_ar نفسه،
# فخوارزمية Unicode Bidi كانت بتشوّه ترتيب العرض. هنا بنستخرج التوكن ده
# لحقل Product.size المنفصل الجديد ونشيله من الاسم.
#
# محافظ عمدًا: بيتعرف بس على مقاسات الملابس القياسية (S/M/L/XL/XXL/XXXL)
# في نهاية الاسم (بمسافة أو شرطة أو قوس قبلها) — مش أي رقم أو حرف لاتيني
# عشان نتجنب لخبطة كود منتج حقيقي جوه الاسم بالغلط. أي حالة تانية (مقاس
# رقمي، صيغة غريبة) تتحل يدويًا من فورم تعديل المنتج بعد كده.
import re

from django.db import migrations

SIZE_RE = re.compile(
    r'\s*[\-\(]?\s*(XXXL|XXL|XL|S|M|L)\s*\)?\s*$',
    re.IGNORECASE,
)


def extract_size_forward(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    updated = 0
    for product in Product.objects.exclude(name_ar=''):
        match = SIZE_RE.search(product.name_ar)
        if not match:
            continue
        size_token = match.group(1).upper()
        cleaned_name = product.name_ar[:match.start()].strip()
        # لو التنضيف سيب اسم فاضي (يعني كل الاسم كان مجرد المقاس)، تجاهل
        # الصف ده بدل ما نمسح الاسم بالكامل — أأمن، وبيتراجع يدويًا لو حصل.
        if not cleaned_name:
            continue
        product.name_ar = cleaned_name
        product.size = size_token
        product.save(update_fields=['name_ar', 'size'])
        updated += 1


def extract_size_backward(apps, schema_editor):
    # عكس الترحيل: نرجّع المقاس لآخر الاسم زي ما كان (best-effort، مش
    # بالضرورة نفس الفواصل الأصلية بالظبط).
    Product = apps.get_model('products', 'Product')
    for product in Product.objects.exclude(size=''):
        product.name_ar = f'{product.name_ar} {product.size}'.strip()
        product.size = ''
        product.save(update_fields=['name_ar', 'size'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0016_productvariantgroup_product_complementary_products_and_more'),
    ]

    operations = [
        migrations.RunPython(extract_size_forward, extract_size_backward),
    ]
