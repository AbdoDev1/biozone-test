from django.db import migrations


def migrate_medium_units(apps, schema_editor):
    """
    ترحيل آمن لأي وحدة size='M' موجودة فعليًا (لو موجودة) — بما إننا بقينا
    نقتصر على وحدتين بس (صغرى/كبرى):
    - لو المنتج معندوش وحدة L: نحوّل M → L (تعتبر هي الوحدة الكبرى).
    - وإلا لو المنتج معندوش وحدة S: نحوّل M → S.
    - وإلا (المنتج عنده S و L بالفعل + M كمان — تلات وحدات فعليًا): نسيب
      القيمة زي ما هي ونطبع تحذير في الـ log عشان الأدمن يراجعها يدويًا
      من لوحة التحكم (مش أمن نحذفها أو ندمجها تلقائيًا من غير قرار بشري).
    """
    ProductUnit = apps.get_model('products', 'ProductUnit')
    medium_units = ProductUnit.objects.filter(size='M').select_related('product')

    if not medium_units.exists():
        return

    needs_manual_review = []

    for unit in medium_units:
        sibling_sizes = set(
            ProductUnit.objects.filter(product_id=unit.product_id)
            .exclude(pk=unit.pk)
            .values_list('size', flat=True)
        )
        if 'L' not in sibling_sizes:
            unit.size = 'L'
            unit.save(update_fields=['size'])
        elif 'S' not in sibling_sizes:
            unit.size = 'S'
            unit.save(update_fields=['size'])
        else:
            needs_manual_review.append(unit)

    if needs_manual_review:
        print(
            '\n⚠️  تنبيه: الوحدات دي عندها 3 أحجام فعليًا (S/M/L) لنفس المنتج '
            'ومحتاجة مراجعة يدوية من الأدمن (دمج أو حذف الزيادة):'
        )
        for unit in needs_manual_review:
            print(f'   - Product #{unit.product_id} / ProductUnit #{unit.pk} ({unit.name})')


def reverse_noop(apps, schema_editor):
    # مفيش رجوع منطقي — القرار كان بشري في حالة التعارض الثلاثي، والباقي
    # تحويل بسيط ما يستحقش reverse تلقائي.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_alter_productunit_size'),
    ]

    operations = [
        migrations.RunPython(migrate_medium_units, reverse_noop),
    ]
