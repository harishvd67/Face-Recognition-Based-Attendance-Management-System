import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import migrations


def backfill_face_images(apps, schema_editor):
    UserProfile = apps.get_model("Students", "UserProfile")
    StudentFaceImage = apps.get_model("Students", "StudentFaceImage")
    media_root = settings.MEDIA_ROOT

    for student in UserProfile.objects.all():
        # Support both the original media/<loginid> layout and the current
        # media/face_images/<date>/<loginid> upload layout.
        folders = [
            os.path.join(media_root, student.loginid),
            os.path.join(media_root, "face_images"),
        ]
        for folder in folders:
            if not os.path.isdir(folder):
                continue
            for root, _, filenames in os.walk(folder):
                for filename in sorted(filenames):
                    path = os.path.join(root, filename)
                    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue
                    relative_path = os.path.relpath(path, media_root)
                    if StudentFaceImage.objects.filter(student=student, image=relative_path).exists():
                        continue
                    if student.loginid not in relative_path.split(os.sep):
                        continue
                    with open(path, "rb") as image_file:
                        StudentFaceImage.objects.create(
                            student=student,
                            image=ContentFile(image_file.read(), name=relative_path),
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
