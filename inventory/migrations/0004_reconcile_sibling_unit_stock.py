from django.db import migrations


def reconcile_forward(apps, schema_editor):
    """
    لكل منتج عنده وحدتين (كبرى وصغرى) وكلاهما مش قابل للتجزئة: نوحّد
    الرصيدين المنفصلين الحاليين في مرجع واحد بالقطعة (الوحدة الصغرى)،
    ثم نعيد حساب الوحدة الكبرى منه بقسمة صحيحة لتحت.
    القاعدة: الصغرى الحالية + (الكبرى الحالية × qty_in_small بتاع الكبرى).
    """
    Product = apps.get_model('products', 'Product')
    Inventory = apps.get_model('inventory', 'Inventory')

    for product in Product.objects.all():
        units = list(product.units.all())
        if len(units) != 2:
            continue
        if any(u.allow_split for u in units):
            continue
        units.sort(key=lambda u: u.qty_in_small)
        small, large = units[0], units[1]

        small_inv, _ = Inventory.objects.get_or_create(
            product_unit=small, defaults={'quantity': 0, 'reserved': 0, 'min_quantity': 0}
        )
        large_inv, _ = Inventory.objects.get_or_create(
            product_unit=large, defaults={'quantity': 0, 'reserved': 0, 'min_quantity': 0}
        )

        factor = large.qty_in_small or 1
        canonical_qty = small_inv.quantity + large_inv.quantity * factor
        canonical_reserved = small_inv.reserved + large_inv.reserved * factor

        small_inv.quantity = canonical_qty
        small_inv.reserved = canonical_reserved
        small_inv.save()

        large_inv.quantity = canonical_qty // factor
        large_inv.reserved = canonical_reserved // factor
        large_inv.save()


def reconcile_backward(apps, schema_editor):
    # مفيش رجوع للحالة القديمة — كانت أرقام متعارضة أصلاً، مفيش داعي نرجعلها.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_stockmovement_out_reserved'),
        ('products', '0007_migrate_medium_units'),
    ]

    operations = [
        migrations.RunPython(reconcile_forward, reconcile_backward),
    ]
