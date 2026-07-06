from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventory',
            name='is_available',
            field=models.BooleanField(
                default=True,
                verbose_name='متوفر في الكتالوج',
                help_text='يتم تحديثه تلقائياً عند انخفاض الكمية، أو يمكن التحكم فيه يدوياً'
            ),
        ),
    ]
