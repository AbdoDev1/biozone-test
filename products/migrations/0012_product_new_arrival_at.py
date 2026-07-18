from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_product_code_name_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='new_arrival_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
