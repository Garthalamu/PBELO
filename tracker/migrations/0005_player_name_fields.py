from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0004_remove_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='first_name',
            field=models.CharField(blank=True, default='', max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='player',
            name='last_name',
            field=models.CharField(blank=True, default='', max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='player',
            name='nickname',
            field=models.CharField(blank=True, default='', max_length=50),
            preserve_default=False,
        ),
    ]
