from django.db import migrations, models
import django.db.models.deletion


def backfill_longfellow(apps, schema_editor):
    Location = apps.get_model("tracker", "Location")
    Game = apps.get_model("tracker", "Game")
    longfellow, _ = Location.objects.get_or_create(name="Longfellow")
    Game.objects.filter(location__isnull=True).update(location=longfellow)


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0002_location_game_location"),
    ]

    operations = [
        migrations.RunPython(backfill_longfellow, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="game",
            name="location",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="games",
                to="tracker.location",
            ),
        ),
    ]
