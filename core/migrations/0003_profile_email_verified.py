from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_event_contactmessage_user_profile_loginactivity_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
    ]
