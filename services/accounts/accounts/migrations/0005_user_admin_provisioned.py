from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_grant_device_metadata")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="admin_provisioned",
            field=models.BooleanField(default=False),
        ),
    ]
