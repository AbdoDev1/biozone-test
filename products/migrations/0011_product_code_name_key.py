# Generated manually on 2026-07-17 — إضافة كود الصنف والاسم المُطبَّع لحل
# مشكلة تكرار الأصناف عند رفع شيت إكسل (راجع staff/views/products.py
# وproducts/matching.py).

from django.db import migrations, models


def backfill_code_and_name_key(apps, schema_editor):
    """
    بيولّد كود فريد (BZ-00001, BZ-00002, ...) لكل منتج موجود بالفعل ومالوش
    كود، وبيحسب name_key من name_ar الحالي. لازم يحصل قبل ما نفعّل قيد
    unique على code في الهجرة اللي بعد كده، عشان القيمة الافتراضية '' مش
    ممكن تتكرر على أكتر من صف.
    """
    Product = apps.get_model('products', 'Product')
    from products.matching import normalize_name

    next_num = 1
    for product in Product.objects.order_by('id'):
        update_fields = []
        if not product.code:
            product.code = f'BZ-{next_num:05d}'
            next_num += 1
            update_fields.append('code')
        new_key = normalize_name(product.name_ar)
        if product.name_key != new_key:
            product.name_key = new_key
            update_fields.append('name_key')
        if update_fields:
            product.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_unitdiscount'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='code',
            field=models.CharField(blank=True, default='', editable=False, max_length=20),
        ),
        migrations.AddField(
            model_name='product',
            name='name_key',
            field=models.CharField(blank=True, db_index=True, default='', editable=False, max_length=255),
        ),
        migrations.RunPython(backfill_code_and_name_key, noop_reverse),
        migrations.AlterField(
            model_name='product',
            name='code',
            field=models.CharField(blank=True, editable=False, max_length=20, unique=True),
        ),
    ]
