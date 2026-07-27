from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Tag(models.Model):
    """
    وسم عام قابل لإعادة الاستخدام على أي كيان في النظام — راجع "مرحلة 4"
    في ROADMAP.md. النهارده بيُستخدم على الطلبات بس (مثلاً "عاجل"،
    "يحتاج مراجعة")، لكن الموديل مش مقفول على الطلبات: أي كيان تاني
    (منتج، عميل، ...) يقدر يستخدم نفس الوسوم من غير أي migration جديدة،
    لأن الربط عن طريق TaggedItem (ContentType عام) مش FK مباشر هنا.

    الوسم نفسه (الاسم واللون) كيان مستقل بيتشارك بين كل الكيانات — يعني
    وسم "عاجل" اتعمل مرة واحدة، ولو استخدمته على طلب وعلى منتج، الاتنين
    بيشاوروا لنفس صف Tag، فتغيير لونه مثلاً بيتغيّر في كل مكان مستخدم فيه.
    """
    class Color(models.TextChoices):
        GRAY = 'gray', 'رمادي'
        RED = 'red', 'أحمر'
        ORANGE = 'orange', 'برتقالي'
        YELLOW = 'yellow', 'أصفر'
        GREEN = 'green', 'أخضر'
        BLUE = 'blue', 'أزرق'
        PURPLE = 'purple', 'بنفسجي'

    name = models.CharField(max_length=50, unique=True, verbose_name='اسم الوسم')
    color = models.CharField(max_length=10, choices=Color.choices, default=Color.GRAY, verbose_name='اللون')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'وسم'
        verbose_name_plural = 'الوسوم'
        ordering = ['name']

    def __str__(self):
        return self.name


class TaggedItem(models.Model):
    """
    ربط وسم بأي كيان — بنفس فكرة activity.ActivityLog (ContentType +
    object_id) بدل FK مباشر لموديل معيّن. UniqueConstraint تحت بيمنع
    تكرار نفس الوسم على نفس العنصر مرتين.
    """
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='tagged_items')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tagged_items_created',
    )

    class Meta:
        verbose_name = 'وسم على عنصر'
        verbose_name_plural = 'وسوم العناصر'
        ordering = ['tag__name']
        constraints = [
            models.UniqueConstraint(fields=['tag', 'content_type', 'object_id'], name='unique_tag_per_item'),
        ]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.tag.name} — {self.content_type.name} #{self.object_id}'
