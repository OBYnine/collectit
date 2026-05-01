from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("collectibles", "0003_wishlist"),
    ]

    operations = [
        migrations.RemoveField(model_name="item", name="category"),
        migrations.RemoveField(model_name="item", name="year"),
        migrations.RemoveField(model_name="item", name="is_for_trade"),
        migrations.DeleteModel(name="Category"),
    ]
