from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_orderitem_purchase_mode'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='orderitem',
            name='purchase_mode',
        ),
    ]
