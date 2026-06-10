from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_player_name_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='player',
            name='name',
        ),
    ]
