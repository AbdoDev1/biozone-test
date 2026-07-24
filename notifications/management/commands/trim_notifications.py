from django.core.management.base import BaseCommand

from notifications.models import Notification
from notifications.services import MAX_NOTIFICATIONS_PER_USER, _trim_old


class Command(BaseCommand):
    help = (
        f'يمسح الإشعارات الأقدم من آخر {MAX_NOTIFICATIONS_PER_USER} لكل '
        'مستخدم. مفيد لتنظيف أي رصيد قديم اتراكم قبل ما الحد ده يتفعّل '
        '(الإنشاء الجديد بقى بيتقلّم أول بأول لوحده — راجع notifications/'
        'services.py). آمن يتنفذ أكتر من مرة، وممكن يتحط في cron دوري '
        'كشبكة أمان لو أي حد إشعارات في المستقبل اتعمل من غير المرور '
        'بدوال notifications.services.'
    )

    def handle(self, *args, **options):
        recipient_ids = (
            Notification.objects.values_list('recipient_id', flat=True).distinct()
        )
        total_deleted = 0
        for recipient_id in recipient_ids:
            before = Notification.objects.filter(recipient_id=recipient_id).count()
            _trim_old(recipient_id)
            after = Notification.objects.filter(recipient_id=recipient_id).count()
            total_deleted += before - after

        self.stdout.write(self.style.SUCCESS(
            f'تم مسح {total_deleted} إشعار قديم زيادة عن الحد ({MAX_NOTIFICATIONS_PER_USER} لكل مستخدم).'
        ))
