from django.db import models
from django.core.exceptions import ValidationError

from accounts.models import User


class AccountTransaction(models.Model):
    """
    حركة واحدة في حساب العميل — دفتر أستاذ بسيط (ledger).
    كل حركة إما:
      - فاتورة (INVOICE): بتتولّد تلقائيًا لحظة إصدار أي فاتورة، وبتزوّد مديونية العميل.
      - دفعة (PAYMENT): بتتسجّل يدويًا من الستاف لما العميل يسدّد، وبتقلّل المديونية.
      - تسوية (ADJUSTMENT): تصحيح يدوي من الستاف (خصم/إضافة استثنائية) لأي سبب غير الفاتورة/الدفعة العادية.

    المديونية الحالية لأي عميل = مجموع amount لكل حركاته (موجب = عليه، سالب/صفر = مفيش عليه أو له رصيد).
    كشف الحساب = نفس الحركات دي مرتبة بالتاريخ مع رصيد تراكمي بعد كل حركة.
    """
    class Kind(models.TextChoices):
        INVOICE = 'INVOICE', 'فاتورة'
        PAYMENT = 'PAYMENT', 'دفعة'
        ADJUSTMENT = 'ADJUSTMENT', 'تسوية'

    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'كاش'
        TRANSFER = 'TRANSFER', 'تحويل بنكي'
        CHEQUE = 'CHEQUE', 'شيك'

    client = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='account_transactions',
        limit_choices_to={'role': 'CLIENT'},
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='موجب = بيزوّد مديونية العميل، سالب = بيقلّلها.',
    )
    invoice = models.ForeignKey(
        'invoices.Invoice', on_delete=models.PROTECT, null=True, blank=True,
        related_name='account_transactions',
    )
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True)
    note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'حركة حساب'
        verbose_name_plural = 'حركات الحسابات'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_kind_display()} — {self.client.username} — {self.amount}'

    def clean(self):
        if self.kind == self.Kind.INVOICE and self.amount <= 0:
            raise ValidationError({'amount': 'حركة الفاتورة لازم تكون قيمة موجبة (بتزوّد المديونية).'})
        if self.kind == self.Kind.PAYMENT and self.amount >= 0:
            raise ValidationError({'amount': 'حركة الدفعة لازم تكون قيمة سالبة (بتقلّل المديونية).'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def balance_for(cls, client):
        """المديونية الحالية للعميل. موجب = عليه فلوس، صفر أو سالب = مفيش عليه/له رصيد."""
        total = cls.objects.filter(client=client).aggregate(total=models.Sum('amount'))['total']
        return total or 0
