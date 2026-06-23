from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0008_alter_player_options"),
    ]

    operations = [
        # Wipe EloChange rows — incompatible scale with OpenSkill; ratings will
        # be rebuilt from scratch via recalculate after Phase 2 is complete.
        migrations.RunSQL("DELETE FROM tracker_elochange;", migrations.RunSQL.noop),

        migrations.RenameModel("EloChange", "RatingChange"),

        migrations.RemoveField("RatingChange", "elo_before"),
        migrations.RemoveField("RatingChange", "elo_after"),

        migrations.AddField(
            "RatingChange",
            "mu_before",
            models.FloatField(default=25.0),
        ),
        migrations.AddField(
            "RatingChange",
            "sigma_before",
            models.FloatField(default=25.0 / 3),
        ),
        migrations.AddField(
            "RatingChange",
            "mu_after",
            models.FloatField(default=25.0),
        ),
        migrations.AddField(
            "RatingChange",
            "sigma_after",
            models.FloatField(default=25.0 / 3),
        ),

        migrations.RemoveField("Player", "singles_elo"),
        migrations.RemoveField("Player", "doubles_elo"),

        migrations.AddField(
            "Player",
            "singles_mu",
            models.FloatField(default=25.0),
        ),
        migrations.AddField(
            "Player",
            "singles_sigma",
            models.FloatField(default=25.0 / 3),
        ),
        migrations.AddField(
            "Player",
            "doubles_mu",
            models.FloatField(default=25.0),
        ),
        migrations.AddField(
            "Player",
            "doubles_sigma",
            models.FloatField(default=25.0 / 3),
        ),
    ]
