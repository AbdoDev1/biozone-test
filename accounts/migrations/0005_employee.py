from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_can_access_accounting'),
    ]

    operations = [
        migrations.CreateModel(
            name='Employee',
            fields=[],
            options={
                'verbose_name': 'موظف',
                'verbose_name_plural': 'الموظفين',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('accounts.user',),
        ),
    ]
