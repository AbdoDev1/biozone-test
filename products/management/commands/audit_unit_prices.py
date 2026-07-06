"""
أمر إدارة يفحص كل المنتجات اللي عندها وحدة صغرى (قطعة) ووحدة كبرى (كرتونة)
مع بعض، ويطلع تقرير بأي وحدة كبرى سعرها (unit_price) غير منطقي مقارنة
بالوحدة الصغرى — أشهر غلطة: سعر الكرتونة اتسجّل بالغلط = سعر القطعة الواحدة
(بدل سعر القطعة × عدد القطع)، فلما خصم الجملة بيتطبّق عليها بيطلع رقم صغير
جدًا وغلط تمامًا (زي ما ظهر في لقطة الشاشة: 44.10 بدل السعر الصحيح للكرتونة).

الأمر Report-only دايمًا — مبيعدّلش أي بيانات، لأن سعر الكرتونة الصحيح ممكن
يكون فيه تفاوض/خصم كمية حقيقي مش بالضرورة = سعر القطعة × العدد بالظبط،
فمينفعش نصلحه أوتوماتيك من غير مراجعة بشري.

الاستخدام:
    python manage.py audit_unit_prices
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from products.models import Product


class Command(BaseCommand):
    help = (
        'يفحص كل منتج عنده وحدة صغرى وكبرى مع بعض، ويطلع تحذير لو سعر الكرتونة '
        '(الوحدة الكبرى) مش منطقي مقارنة بسعر القطعة (الوحدة الصغرى) — زي ما لو '
        'كان أقل من أو يساوي سعر القطعة، أو أقل بكتير من (سعر القطعة × عدد القطع). '
        'Report-only، مفيش أي تعديل فعلي على البيانات.'
    )

    # لو سعر الكرتونة أقل من (سعر القطعة × العدد) بنسبة أكبر من كده، بنعتبره
    # مريب ويستاهل مراجعة — نسبة مرنة عشان خصومات الجملة الحقيقية مش بالضرورة
    # صفر، لكن مش المفروض تتجاوز نص السعر غالبًا.
    # لازم تكون Decimal مش float عشان unit_price نفسه Decimal، وبايثون مبيسمحش
    # تضرب Decimal في float مباشرة (TypeError).
    SUSPICIOUS_DROP_RATIO = Decimal('0.5')

    def handle(self, *args, **options):
        products = Product.objects.prefetch_related('units').all()
        problems = []

        for product in products:
            units = {u.size: u for u in product.units.all()}
            small = units.get('S')
            large = units.get('L')

            if not small or not large:
                continue  # مفيش مقارنة ممكنة لو المنتج بوحدة واحدة بس

            expected_large = small.unit_price * large.qty_in_small

            if large.unit_price <= small.unit_price:
                problems.append(
                    f'❌ {product.display_name}: سعر الكرتونة ({large.unit_price}) '
                    f'أقل من أو يساوي سعر القطعة ({small.unit_price})! '
                    f'شكله سعر الكرتونة اتسجّل غلط = سعر قطعة. '
                    f'(الكرتونة فيها {large.qty_in_small} قطعة، السعر المتوقع تقريبًا {expected_large})'
                )
            elif expected_large and large.unit_price < expected_large * self.SUSPICIOUS_DROP_RATIO:
                problems.append(
                    f'⚠ {product.display_name}: سعر الكرتونة ({large.unit_price}) أقل بكتير من '
                    f'المتوقع (~{expected_large} = سعر القطعة {small.unit_price} × {large.qty_in_small} قطعة). '
                    f'يستاهل مراجعة — يمكن مقصود (خصم كمية حقيقي) ويمكن غلطة إدخال.'
                )

        if not problems:
            self.stdout.write(self.style.SUCCESS('كل أسعار الكراتين شكلها منطقي مقارنة بأسعار القطع. مفيش حاجة تستاهل مراجعة.'))
            return

        self.stdout.write(self.style.WARNING(f'لقيت {len(problems)} حالة تستاهل مراجعة:\n'))
        for p in problems:
            self.stdout.write(f'  {p}\n')
