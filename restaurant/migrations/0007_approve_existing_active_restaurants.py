from django.db import migrations


def approve_existing_active_restaurants(apps, schema_editor):
    Restaurant = apps.get_model("restaurant", "Restaurant")
    Restaurant.objects.filter(is_active=True, status="pending").update(status="approved")


class Migration(migrations.Migration):
    dependencies = [
        ("restaurant", "0006_alter_restaurant_is_active"),
    ]

    operations = [
        migrations.RunPython(
            approve_existing_active_restaurants,
            migrations.RunPython.noop,
        ),
    ]