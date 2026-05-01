from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("collectibles", "0004_cleanup_item_fields"),
    ]

    operations = [
        migrations.RemoveField(model_name="item", name="condition"),
    ]
