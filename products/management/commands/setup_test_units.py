"""
أمر إدارة لضبط قيم اختبارية منطقية لـ qty_in_small و allow_split على
المنتجات الموجودة فعليًا في قاعدة بياناتك — بدل ما تفضل كل الوحدات الكبرى
بقيمة افتراضية (1) اللي معناها عمليًا إن مفيش فرق حقيقي بين سعر الجملة
والقطاعي في الكمية (مبني على qty_in_small).

الأمر Dry-run افتراضيًا (تقرير بس، مفيش تعديل فعلي) — استخدم --apply
عشان يتطبّق فعليًا على قاعدة البيانات.

الاستخدام:
    python manage.py setup_test_units                 # تقرير معاينة فقط
    python manage.py setup_test_units --apply          # تطبيق فعلي
    python manage.py setup_test_units --apply --default-qty 30
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import Product, ProductUnit


# heuristics: كلمة مفتاحية في اسم المنتج (عربي) → (qty_in_small مقترحة, allow_split مقترح)
# القيم دي تقريبية لأغراض الاختبار بس — عدّلها من الأدمن براحتك بعد كده لكل منتج.
QTY_HEURISTICS = [
    (['سرنج', 'ابرة', 'إبرة', 'كانيولا'], 100, True),
    (['قفاز', 'كمام'], 100, True),
    (['شاش', 'قطن', 'كمادة', 'ضمادة', 'رباط'], 50, True),
    (['محلول', 'سيرم', 'انفيوجن', 'إنفيوجن'], 20, False),
    (['بنج', 'امبول', 'أمبول', 'فيال', 'حقن'], 50, False),
]
DEFAULT_QTY = 50
DEFAULT_ALLOW_SPLIT = False


def guess_qty_and_split(name):
    name = name or ''
    for keywords, qty, allow_split in QTY_HEURISTICS:
        if any(k in name for k in keywords):
            return qty, allow_split
    return DEFAULT_QTY, DEFAULT_ALLOW_SPLIT


class Command(BaseCommand):
    help = (
        'يمر على كل المنتجات ويقترح/يضبط qty_in_small (وallow_split لو '
        'المنتج بوحدة واحدة) لأغراض اختبار فيتشر التجزئة والتسعير حسب '
        'الكمية. Dry-run افتراضيًا — استخدم --apply للتطبيق الفعلي.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='طبّق التغييرات فعليًا (بدل التقرير بس).',
        )
        parser.add_argument(
            '--default-qty', type=int, default=DEFAULT_QTY,
            help=f'القيمة الافتراضية لو مفيش كلمة مفتاحية اتطابقت (افتراضي {DEFAULT_QTY}).',
        )
        parser.add_argument(
            '--only-unset', action='store_true', default=True,
            help='(افتراضي مفعّل) عدّل بس الوحدات اللي qty_in_small عندها 0 أو 1 — ما يلمسش قيم مدخلة فعليًا من قبل.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        default_qty = options['default_qty']

        changed_qty = 0
        changed_split = 0
        skipped = 0

        products = Product.objects.prefetch_related('units').all()

        with transaction.atomic():
            for product in products:
                units = list(product.units.all())
                if not units:
                    continue

                units_sorted = sorted(units, key=lambda u: u.qty_in_small)
                large = units_sorted[-1]
                name = product.name_ar or product.name_en or ''

                if large.qty_in_small not in (0, 1):
                    # الوحدة دي فيها قيمة حقيقية مدخلة بالفعل — ما نلمسهاش
                    skipped += 1
                    continue

                suggested_qty, suggested_split = guess_qty_and_split(name)

                changes = []
                if large.qty_in_small in (0, 1):
                    changes.append(f'qty_in_small: {large.qty_in_small} → {suggested_qty}')

                # allow_split بس منطقي لمنتج بوحدة واحدة (مفيش قطعة منفصلة أصلًا)
                is_single_unit_product = len(units) == 1
                will_set_split = is_single_unit_product and not large.allow_split and suggested_split
                if will_set_split:
                    changes.append('allow_split: False → True')

                if not changes:
                    continue

                self.stdout.write(
                    f'{product.display_name} → وحدة "{large.name}": ' + '، '.join(changes)
                )

                if apply_changes:
                    large.qty_in_small = suggested_qty
                    if will_set_split:
                        large.allow_split = True
                    large.save(update_fields=['qty_in_small', 'allow_split'])
                    changed_qty += 1
                    if will_set_split:
                        changed_split += 1

            if not apply_changes:
                # في dry-run، نرجع الترانزاكشن للخلف عشان نضمن مفيش أي حفظ فعلي حصل بالغلط
                transaction.set_rollback(True)

        self.stdout.write('')
        if apply_changes:
            self.stdout.write(self.style.SUCCESS(
                f'تم تحديث {changed_qty} وحدة كبرى ({changed_split} منهم اتفعّل عليهم allow_split). '
                f'اتخطّى {skipped} وحدة كان عندها قيمة مدخلة بالفعل.'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'ده وضع المعاينة بس (dry-run) — مفيش أي حاجة اتغيّرت في قاعدة البيانات. '
                'شغّل الأمر تاني بـ --apply عشان يتطبّق فعليًا:'
            ))
            self.stdout.write(self.style.WARNING('  python manage.py setup_test_units --apply'))
