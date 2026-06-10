from django.db import migrations


def populate_name_fields(apps, schema_editor):
    Player = apps.get_model('tracker', 'Player')
    for player in Player.objects.all():
        parts = player.name.split()
        if len(parts) >= 2:
            player.first_name = parts[0]
            player.last_name = ' '.join(parts[1:])
        else:
            player.nickname = parts[0] if parts else ''
        player.save()


def reverse_populate(apps, schema_editor):
    Player = apps.get_model('tracker', 'Player')
    for player in Player.objects.all():
        if player.first_name or player.last_name:
            player.name = f"{player.first_name} {player.last_name}".strip()
        else:
            player.name = player.nickname
        player.save()


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0005_player_name_fields'),
    ]

    operations = [
        migrations.RunPython(populate_name_fields, reverse_populate),
    ]
