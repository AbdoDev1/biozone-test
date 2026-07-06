from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_inventory_is_available'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='movement_type',
            field=models.CharField(
                choices=[
                    ('IN', 'وارد'),
                    ('OUT', 'صادر (مباشر)'),
                    ('OUT_RESERVED', 'صادر (من محجوز عند التسليم)'),
                    ('RESERVE', 'حجز'),
                    ('RELEASE', 'إلغاء حجز'),
                ],
                max_length=13,
            ),
        ),
    ]
