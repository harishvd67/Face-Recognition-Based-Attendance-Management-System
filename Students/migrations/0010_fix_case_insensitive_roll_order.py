from django.db import migrations


ROLL_PREFIX = "24AK1F"


def fix_roll_order(apps, schema_editor):
    UserProfile = apps.get_model("Students", "UserProfile")
    DailyAttendance = apps.get_model("Students", "DailyAttendance")

    students = list(UserProfile.objects.all())
    students.sort(key=lambda student: (student.name.casefold(), student.loginid.casefold()))

    for student in students:
        student.roll_number = f"__reassign__{student.pk}"
        student.save(update_fields=["roll_number"])

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


def reverse_fix(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("Students", "0009_assign_roll_numbers"),
    ]

    operations = [
        migrations.RunPython(fix_roll_order, reverse_fix),
    ]
