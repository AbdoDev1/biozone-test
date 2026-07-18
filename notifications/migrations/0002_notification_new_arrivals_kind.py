from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='kind',
            field=models.CharField(choices=[
                ('NEW_ORDER', 'طلب جديد'),
                ('ORDER_NEEDS_APPROVAL', 'طلب يحتاج موافقتك على تعديل'),
                ('ORDER_CONFIRMED', 'تم تأكيد الطلب'),
                ('ORDER_REJECTED', 'تم رفض الطلب'),
                ('ORDER_DELIVERED', 'تم تسليم الطلب'),
                ('CLIENT_APPROVED_AMENDMENT', 'العميل وافق على التعديل'),
                ('CLIENT_REJECTED_AMENDMENT', 'العميل رفض التعديل'),
                ('NEW_CLIENT_REGISTRATION', 'طلب تسجيل عميل جديد'),
                ('NEW_ARRIVALS', 'وارد جديد في المتجر'),
            ], max_length=40),
        ),
    ]
