from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_add_is_news_editor"),
    ]

    operations = [
        migrations.DeleteModel(name="Follow"),
        migrations.RemoveField(model_name="user", name="level"),
        migrations.RemoveField(model_name="user", name="xp"),
        migrations.RemoveField(model_name="user", name="xp_to_next"),
        migrations.RemoveField(model_name="user", name="is_pro"),
        migrations.RemoveField(model_name="user", name="followers_count"),
    ]
