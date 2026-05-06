from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0003_supportmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportticket',
            name='resolved_confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
