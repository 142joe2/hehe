from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core_system", "0067_memberregistrationrequest_password_hash"),
    ]
    operations = [
        migrations.AddField(
            model_name="member",
            name="profile_picture",
            field=models.ImageField(blank=True, null=True, upload_to="profile_pics/"),
        ),
    ]
