from django.db import migrations


ROLL_PREFIX = "24AK1F"


def assign_roll_numbers(apps, schema_editor):
    UserProfile = apps.get_model("Students", "UserProfile")
    DailyAttendance = apps.get_model("Students", "DailyAttendance")

    students = list(UserProfile.objects.all().order_by("name", "loginid"))
    roll_numbers = {}
    for index, student in enumerate(students, 1):
        roll_number = f"{ROLL_PREFIX}{index:04d}"
        student.roll_number = roll_number
        student.save(update_fields=["roll_number"])
        roll_numbers[student.loginid] = roll_number

    for record in DailyAttendance.objects.all():
        roll_number = roll_numbers.get(record.student_id)
        if roll_number:
            record.roll_number = roll_number
            record.save(update_fields=["roll_number"])


def reverse_assignments(apps, schema_editor):
    UserProfile = apps.get_model("Students", "UserProfile")
    DailyAttendance = apps.get_model("Students", "DailyAttendance")
    UserProfile.objects.update(roll_number=None)
    DailyAttendance.objects.update(roll_number="")


class Migration(migrations.Migration):
    dependencies = [
        ("Students", "0008_dailyattendance_roll_number_userprofile_roll_number"),
    ]

    operations = [
        migrations.RunPython(assign_roll_numbers, reverse_assignments),
    ]
