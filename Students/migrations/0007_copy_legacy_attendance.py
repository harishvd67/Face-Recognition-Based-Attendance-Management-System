from django.db import migrations


def copy_legacy_attendance(apps, schema_editor):
    Attendance = apps.get_model("Students", "Attendance")
    DailyAttendance = apps.get_model("Students", "DailyAttendance")
    UserProfile = apps.get_model("Students", "UserProfile")

    names = {
        student.loginid: student.name
        for student in UserProfile.objects.all().only("loginid", "name")
    }

    for record in Attendance.objects.all().order_by("date", "timestamp"):
        daily, _ = DailyAttendance.objects.get_or_create(
            student_id=record.student_id,
            date=record.date,
            defaults={
                "student_name": names.get(record.student_id, record.student_id),
                "status": "Present",
                "attendance_time": record.timestamp,
            },
        )
        period_field = f"period_{record.period[1:]}" if record.period.startswith("P") else None
        if period_field and hasattr(daily, period_field):
            setattr(daily, period_field, "Present")
        daily.status = "Present"
        if daily.attendance_time is None:
            daily.attendance_time = record.timestamp
        daily.save()


def reverse_copy(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("Students", "0006_dailyattendance"),
    ]

    operations = [
        migrations.RunPython(copy_legacy_attendance, reverse_copy),
    ]
