from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0004_article_ai_source_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="source_url",
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
    ]
