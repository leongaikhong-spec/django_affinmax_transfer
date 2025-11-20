# Generated migration for callback_attempts field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transfer', '0010_add_callback_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactionslist',
            name='callback_attempts',
            field=models.IntegerField(db_column='callback_attempts', default=0),
        ),
    ]
