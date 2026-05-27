from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0003_cleanup_newstag_coverimage"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="ai_model",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="article",
            name="imported_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="article",
            name="is_ai_generated",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="article",
            name="source_external_id",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
        migrations.AddField(
            model_name="article",
            name="source_published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="article",
            name="source_site",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="article",
            name="source_url",
            field=models.URLField(blank=True, max_length=1000, null=True, unique=True),
        ),
    ]
