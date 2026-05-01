from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0002_add_article_images"),
    ]

    operations = [
        migrations.RemoveField(model_name="article", name="tag"),
        migrations.RemoveField(model_name="article", name="cover_image"),
        migrations.DeleteModel(name="NewsTag"),
    ]
