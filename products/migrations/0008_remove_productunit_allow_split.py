from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_migrate_medium_units'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='productunit',
            name='allow_split',
        ),
        migrations.AlterField(
            model_name='productunit',
            name='qty_in_small',
            field=models.PositiveIntegerField(
                default=1,
                verbose_name='الكمية بالقطعة',
                help_text=(
                    'كام قطعة (وحدة صغرى) داخل الوحدة دي؟ الوحدة الصغرى نفسها = 1 دايمًا. '
                    'الوحدة الكبرى (الكرتونة) = عدد القطع فيها، مثلاً 50. هذا الرقم هو '
                    'معامل التحويل المعتمد عليه في كل حساب مخزون (الرصيد الحقيقي محفوظ '
                    'بالقطعة دايمًا، بغض النظر عن الوحدة اللي بيتم البيع بيها).'
                ),
            ),
        ),
    ]
