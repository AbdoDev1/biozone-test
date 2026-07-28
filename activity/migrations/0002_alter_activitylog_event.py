# Generated manually — adds 'DELETED' to ActivityLog.Event choices
# (نفس الفكرة: تتبع حذف الكيانات اللي مالهاش صفحة تفاصيل مستقلة زي الأقسام).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activitylog',
            name='event',
            field=models.CharField(
                choices=[
                    ('CREATED', 'تم الإنشاء'),
                    ('UPDATED', 'تعديل بيانات'),
                    ('DELETED', 'تم الحذف'),
                    ('NOTE', 'ملاحظة'),
                ],
                max_length=20,
            ),
        ),
    ]
