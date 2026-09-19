from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Students", "0003_alter_attendance_timestamp"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="email",
                field=models.EmailField(blank=True, null=True),
            preserve_default=False,
        ),
    ]