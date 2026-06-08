from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_withdrawalrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="onboarding_completed_steps",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="user",
            name="onboarding_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
