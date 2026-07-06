from django.db import models
from django.db import transaction
from accounts.models import User
from products.models import ProductUnit


class SiteConfig(models.Model):
    """
    إعدادات عامة للموقع — سطر واحد بس (Singleton).
    يتم التعديل عليه من لوحة الأدمن.
    """
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='الحد الأدنى لقيمة الطلب',
        help_text='أقل قيمة إجمالية مسموح بها لإرسال الطلب (بالجنيه). اترك القيمة صفرًا في حال عدم الرغبة في تحديد حد أدنى.',
    )

    class Meta:
        verbose_name = 'إعدادات الموقع'
        verbose_name_plural = 'إعدادات الموقع'

    def __str__(self):
        return 'إعدادات الموقع'

    def save(self, *args, **kwargs):
        # نضمن وجود سطر واحد بس دايمًا (pk=1)
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # منمنع حذف السطر الوحيد
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING         = 'PENDING',         'في الانتظار'
        NEEDS_APPROVAL  = 'NEEDS_APPROVAL',   'بانتظار موافقتك على التعديل'
        CONFIRMED       = 'CONFIRMED',        'مؤكد'
        REJECTED        = 'REJECTED',         'مرفوض'
        DELIVERED       = 'DELIVERED',        'تم التسليم'

    client      = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders')
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'طلب'
        verbose_name_plural = 'الطلبات'
        ordering = ['-created_at']

    def __str__(self):
        return f'طلب #{self.pk} — {self.client.username}'

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def original_total(self):
        return sum(item.original_subtotal for item in self.items.all())

    @property
    def is_amended(self):
        return any(item.is_amended for item in self.items.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_status = self.status

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        status_changed = (not is_new) and (self.status != self._old_status)
        actor = getattr(self, '_actor', None)
        super().save(*args, **kwargs)

        if is_new:
            OrderLog.objects.create(
                order=self,
                event=OrderLog.Event.CREATED,
                note='تم إنشاء الطلب.',
                created_by=actor,
            )
        elif status_changed:
            OrderLog.objects.create(
                order=self,
                event=OrderLog.Event.STATUS_CHANGED,
                note=f'تم تغيير حالة الطلب إلى "{self.get_status_display()}".',
                new_status=self.status,
                created_by=actor,
            )
        self._old_status = self.status

    # ---------- منطق سير العمل (المرحلة 8) ----------

    def confirm(self, actor=None):
        """المخزن بيأكد الطلب من غير أي تعديل في الكميات."""
        self._actor = actor
        self.status = self.Status.CONFIRMED
        self.save()

    @transaction.atomic
    def reject(self, actor=None, reason=''):
        """رفض الطلب (من المخزن أو من العميل) — بيفك كل الحجز المتبقي."""
        from inventory.models import Inventory, StockMovement
        if self.status == self.Status.DELIVERED:
            raise ValueError('الطلب ده اتسلّم بالفعل، مينفعش يترفض.')
        if self.status == self.Status.REJECTED:
            raise ValueError('الطلب ده مرفوض بالفعل.')

        product_ids = [item.product_unit.product_id for item in self.items.all()]
        locked_inventories = {
            inv.product_id: inv
            for inv in Inventory.objects.select_for_update().filter(product_id__in=product_ids)
        }

        for item in self.items.all():
            inv = locked_inventories.get(item.product_unit.product_id)
            if inv and inv.reserved > 0:
                # الحجز اتسجّل بوحدة الصنف (item.product_unit) — بنفك بنفس
                # الوحدة، بحد أقصى المتاح فعليًا محجوز (بالقطعة) محوّل لوحدة الصنف.
                unit = item.product_unit
                release_qty_units = min(item.quantity, inv.reserved // unit.qty_in_small)
                if release_qty_units > 0:
                    StockMovement.objects.create(
                        inventory=inv,
                        unit=unit,
                        movement_type=StockMovement.MovementType.RELEASE,
                        quantity=release_qty_units,
                        note=f'فك حجز بسبب رفض الطلب #{self.pk}',
                        created_by=actor,
                    )
                    inv.refresh_from_db()
        self._actor = actor
        self.status = self.Status.REJECTED
        if reason:
            OrderLog.objects.create(
                order=self, event=OrderLog.Event.NOTE, note=reason, created_by=actor,
            )
        self.save()

    @transaction.atomic
    def mark_delivered(self, actor=None):
        """تسليم الطلب — بيحوّل الكمية المحجوزة لصادر فعلي من المخزون، وبيصدر الفاتورة تلقائيًا."""
        from inventory.models import Inventory, StockMovement
        product_ids = [item.product_unit.product_id for item in self.items.all()]
        locked_inventories = {
            inv.product_id: inv
            for inv in Inventory.objects.select_for_update().filter(product_id__in=product_ids)
        }

        for item in self.items.all():
            inv = locked_inventories.get(item.product_unit.product_id)
            if inv:
                out_movement = StockMovement(
                    inventory=inv,
                    unit=item.product_unit,
                    movement_type=StockMovement.MovementType.OUT_RESERVED,
                    quantity=item.quantity,
                    note=f'تسليم طلب #{self.pk}',
                    created_by=actor,
                )
                out_movement.full_clean()
                out_movement.save()

                release_movement = StockMovement(
                    inventory=inv,
                    unit=item.product_unit,
                    movement_type=StockMovement.MovementType.RELEASE,
                    quantity=item.quantity,
                    note=f'فك حجز بعد تسليم طلب #{self.pk}',
                    created_by=actor,
                )
                release_movement.full_clean()
                release_movement.save()
        self._actor = actor
        self.status = self.Status.DELIVERED
        self.save()

        from invoices.models import Invoice
        Invoice.issue_for_order(self, actor=actor)

    @transaction.atomic
    def amend_item_quantity(self, item, new_quantity, actor=None):
        """
        المخزن بيعدّل كمية صنف في الطلب (لو الكمية المتاحة أقل من المطلوب).
        بيفك/يزود الحجز حسب الفرق، وبيعيد حساب السعر حسب الكمية الجديدة.
        """
        from inventory.models import Inventory, StockMovement
        old_quantity = item.quantity
        diff = new_quantity - old_quantity
        # الفرق بوحدة الصنف نفسها (كرتونة/قطعة) — المزود (StockMovement.save)
        # هو اللي بيحوّلها لقطع بمعامل qty_in_small تلقائيًا.
        unit = item.product_unit

        if diff != 0:
            inv = Inventory.objects.select_for_update().get(product_id=unit.product_id)
            if diff < 0:
                StockMovement.objects.create(
                    inventory=inv,
                    unit=unit,
                    movement_type=StockMovement.MovementType.RELEASE,
                    quantity=abs(diff),
                    note=f'فك حجز جزئي بسبب تعديل الكمية في طلب #{self.pk}',
                    created_by=actor,
                )
            else:
                if diff * unit.qty_in_small > inv.available:
                    raise ValueError('الكمية المطلوبة أكبر من المتاح في المخزون.')
                StockMovement.objects.create(
                    inventory=inv,
                    unit=unit,
                    movement_type=StockMovement.MovementType.RESERVE,
                    quantity=diff,
                    note=f'حجز إضافي بسبب تعديل الكمية في طلب #{self.pk}',
                    created_by=actor,
                )

        item.quantity = new_quantity
        if new_quantity > 0:
            new_subtotal = item.product_unit.get_price(new_quantity, client=self.client)
            item.unit_price = new_subtotal / new_quantity
        item.save()

        OrderLog.objects.create(
            order=self,
            event=OrderLog.Event.NOTE,
            note=(
                f'تم تعديل كمية "{item.product_unit.product.display_name} — '
                f'{item.product_unit.name}" من {old_quantity} إلى {new_quantity}.'
            ),
            created_by=actor,
        )

    def send_for_client_approval(self, actor=None):
        self._actor = actor
        self.status = self.Status.NEEDS_APPROVAL
        self.save()

    @transaction.atomic
    def client_approve_amendment(self, actor=None):
        """العميل وافق على التعديل — يثبّت الكميات الجديدة كأصل ويأكد الطلب."""
        for item in self.items.all():
            item.original_quantity = item.quantity
            item.original_unit_price = item.unit_price
            item.save(update_fields=['original_quantity', 'original_unit_price'])
        self._actor = actor
        self.status = self.Status.CONFIRMED
        self.save()

    def client_reject_amendment(self, actor=None):
        """العميل رفض التعديل — الطلب بالكامل يترفض ويتفك الحجز."""
        self.reject(actor=actor, reason='العميل رفض التعديل المقترح من المخزن.')


class OrderItem(models.Model):
    order        = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_unit = models.ForeignKey(ProductUnit, on_delete=models.PROTECT)
    quantity     = models.PositiveIntegerField()
    unit_price   = models.DecimalField(max_digits=10, decimal_places=2)
    original_quantity   = models.PositiveIntegerField(null=True, blank=True)
    original_unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'صنف في الطلب'
        verbose_name_plural = 'أصناف الطلب'

    def __str__(self):
        return f'{self.product_unit.name} x{self.quantity}'

    @property
    def stock_qty(self):
        """
        الكمية الفعلية بالقطعة اللي اتحجزت/اتطرحت من رصيد المخزون — تحويل
        quantity (بوحدة الطلب: كرتونة للجملة أو قطعة للقطاعي) بمعامل qty_in_small.
        """
        return self.quantity * self.product_unit.qty_in_small

    @property
    def unit_display_label(self):
        return self.product_unit.name

    def save(self, *args, **kwargs):
        # أول مرة بس بنحفظ نسخة من الكمية/السعر الأصلي قبل أي تعديل من المخزن
        if self.original_quantity is None:
            self.original_quantity = self.quantity
        if self.original_unit_price is None:
            self.original_unit_price = self.unit_price
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    @property
    def original_subtotal(self):
        return (self.original_unit_price or self.unit_price) * (self.original_quantity or self.quantity)

    @property
    def is_amended(self):
        return (
            self.original_quantity is not None and self.quantity != self.original_quantity
        ) or (
            self.original_unit_price is not None and self.unit_price != self.original_unit_price
        )


class OrderLog(models.Model):
    """
    سجل عمليات الطلب — كل حدث بيحصل على الطلب (إنشاء، تغيير حالة، ملاحظة).
    العميل يشوفه كـ تايم لاين في صفحة تفاصيل الطلب.
    """
    class Event(models.TextChoices):
        CREATED        = 'CREATED',        'تم إنشاء الطلب'
        STATUS_CHANGED = 'STATUS_CHANGED',  'تغيير الحالة'
        NOTE           = 'NOTE',            'ملاحظة'

    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='logs')
    event      = models.CharField(max_length=20, choices=Event.choices)
    new_status = models.CharField(max_length=20, choices=Order.Status.choices, blank=True)
    note       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='order_logs',
    )

    class Meta:
        verbose_name = 'سجل عملية'
        verbose_name_plural = 'سجل العمليات'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_event_display()} — طلب #{self.order_id}'
