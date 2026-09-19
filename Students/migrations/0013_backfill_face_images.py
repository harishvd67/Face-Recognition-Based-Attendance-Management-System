import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import migrations


def backfill_face_images(apps, schema_editor):
    UserProfile = apps.get_model("Students", "UserProfile")
    StudentFaceImage = apps.get_model("Students", "StudentFaceImage")
    media_root = settings.MEDIA_ROOT

    for student in UserProfile.objects.all():
        folder = os.path.join(media_root, student.loginid)
        if not os.path.isdir(folder):
            continue

        for filename in sorted(os.listdir(folder)):
            path = os.path.join(folder, filename)
            if not os.path.isfile(path) or not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            image_name = f"{student.loginid}/{filename}"
            if StudentFaceImage.objects.filter(student=student, image=image_name).exists():
                continue
            with open(path, "rb") as image_file:
                StudentFaceImage.objects.create(
                    student=student,
                    image=ContentFile(image_file.read(), name=image_name),
                )


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("Students", "0012_remove_dailyattendance_period_4_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_face_images, reverse_backfill),
    ]
