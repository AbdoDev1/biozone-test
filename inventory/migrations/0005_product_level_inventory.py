from django.db import migrations, models
import django.db.models.deletion


def migrate_data_forward(apps, schema_editor):
    """
    من نموذج "رصيد لكل وحدة + مزامنة بين وحدتين شقيقتين" لنموذج "رصيد واحد لكل
    منتج، محفوظ بالقطعة دايمًا". الخطوات:
    1) نسجّل على كل StockMovement قديمة الوحدة اللي كانت مسجّلة بيها فعليًا
       (product_unit بتاع الـ Inventory القديم اللي كانت مربوطة بيه).
    2) لكل منتج: بنجمع كل أرصدة وحداته (محوّلة بالقطعة عن طريق qty_in_small)
       في صف Inventory واحد "فائز"، وبننقل كل الحركات القديمة التابعة لأي صف
       Inventory تاني لنفس المنتج على الصف الفائز ده، ثم نحذف الصفوف الزيادة.
    """
    Product = apps.get_model('products', 'Product')
    Inventory = apps.get_model('inventory', 'Inventory')
    StockMovement = apps.get_model('inventory', 'StockMovement')

    # 1) تسجيل الوحدة الأصلية لكل حركة قبل ما نفقد الرابط القديم (inventory.product_unit)
    for movement in StockMovement.objects.select_related('inventory__product_unit').all():
        movement.unit_id = movement.inventory.product_unit_id
        movement.save(update_fields=['unit'])

    # 2) توحيد كل أرصدة المنتج في صف واحد بالقطعة
    for product in Product.objects.all():
        inventories = list(
            Inventory.objects.select_related('product_unit').filter(product_unit__product_id=product.id)
        )
        if not inventories:
            continue

        # الوحدة الأصغر (qty_in_small الأقل) هي المرجع لو موجودة، وإلا أول صف متاح.
        inventories.sort(key=lambda inv: inv.product_unit.qty_in_small)
        winner = inventories[0]
        winner_factor = winner.product_unit.qty_in_small or 1

        total_qty = winner.quantity * winner_factor
        total_reserved = winner.reserved * winner_factor

        for loser in inventories[1:]:
            factor = loser.product_unit.qty_in_small or 1
            total_qty += loser.quantity * factor
            total_reserved += loser.reserved * factor
            # ننقل الحركات القديمة التابعة لهذا الصف الخاسر على الصف الفائز،
            # عشان نحافظ على سجل الحركات كامل (مفيش داعي نفقد تاريخ الحركات).
            StockMovement.objects.filter(inventory_id=loser.id).update(inventory_id=winner.id)
            loser.delete()

        winner.product_id = product.id
        winner.quantity = total_qty
        winner.reserved = total_reserved
        winner.save(update_fields=['product', 'quantity', 'reserved'])


def migrate_data_backward(apps, schema_editor):
    # مفيش رجوع للنموذج القديم (رصيد منفصل لكل وحدة) — كان أصلاً مصدر المشكلة.
    pass


class Migration(migrations.Migration):

    # على Postgres: خلط تعديلات schema (ALTER/REMOVE) مع تعديلات بيانات
    # ضخمة (RunPython) في transaction واحدة بيسبب
    # "cannot ALTER TABLE because it has pending trigger events" — لأن حذف/تعديل
    # صفوف بيأجّل فحص FK triggers لحد ما الـ transaction يتقفل، وACTION ALTER TABLE
    # بعدها بالظبط بيصطدم بيها. atomic=False بتخلي كل عملية تتنفذ وتتقفل لوحدها.
    atomic = False

    dependencies = [
        ('inventory', '0004_reconcile_sibling_unit_stock'),
        ('products', '0008_remove_productunit_allow_split'),
    ]

    operations = [
        # -- خطوة 1: إضافة الحقول الجديدة (nullable مؤقتًا لحد ما نملأ البيانات) --
        migrations.AddField(
            model_name='inventory',
            name='product',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='inventory_new',
                to='products.product',
            ),
        ),
        migrations.AddField(
            model_name='stockmovement',
            name='unit',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='products.productunit',
                verbose_name='الوحدة',
                help_text='الوحدة اللي اتسجّلت بيها الحركة (كرتونة/قطعة) — الكمية أدناه بوحدة هذه الوحدة.',
            ),
        ),

        # -- خطوة 2: تعبئة/توحيد البيانات --
        migrations.RunPython(migrate_data_forward, migrate_data_backward),

        # -- خطوة 3: حذف الحقول القديمة وتثبيت الحقول الجديدة --
        migrations.RemoveField(
            model_name='inventory',
            name='product_unit',
        ),
        migrations.AlterField(
            model_name='inventory',
            name='product',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='inventory',
                to='products.product',
            ),
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='unit',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to='products.productunit',
                verbose_name='الوحدة',
                help_text='الوحدة اللي اتسجّلت بيها الحركة (كرتونة/قطعة) — الكمية أدناه بوحدة هذه الوحدة.',
            ),
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='quantity',
            field=models.PositiveIntegerField(
                verbose_name='الكمية (بوحدة الحركة)',
                help_text='بوحدة "الوحدة" المختارة أعلاه، مش بالقطعة بالضرورة — النظام بيحوّلها تلقائيًا.',
            ),
        ),
        migrations.AlterField(
            model_name='inventory',
            name='quantity',
            field=models.PositiveIntegerField(default=0, verbose_name='الرصيد (بالقطعة)'),
        ),
        migrations.AlterField(
            model_name='inventory',
            name='reserved',
            field=models.PositiveIntegerField(default=0, verbose_name='المحجوز (بالقطعة)'),
        ),
        migrations.AlterField(
            model_name='inventory',
            name='min_quantity',
            field=models.PositiveIntegerField(default=0, verbose_name='الحد الأدنى (بالقطعة)'),
        ),
    ]
