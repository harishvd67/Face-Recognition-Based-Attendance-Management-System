from django.db import models

# Create your models here.
from django.db import models

class UserProfile(models.Model):
    name = models.CharField(max_length=100)
    loginid = models.CharField(max_length=50, unique=True)
    roll_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    mobile = models.CharField(max_length=10)
    password = models.CharField(max_length=128)  # Store hashed password in production
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.loginid
    
from django.db import models
from django.utils import timezone


class DailyAttendance(models.Model):
    student_id = models.CharField(max_length=100)
    roll_number = models.CharField(max_length=20, default="")
    student_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default="Absent")
    date = models.DateField(default=timezone.localdate)
    attendance_time = models.DateTimeField(null=True, blank=True)
    period_1 = models.CharField(max_length=20, default="Absent")
    period_2 = models.CharField(max_length=20, default="Absent")
    period_3 = models.CharField(max_length=20, default="Absent")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("student_id", "date"),
                name="unique_daily_student_attendance",
            )
        ]

    def __str__(self):
        return f"{self.student_id} - {self.date}"


class StudentFaceImage(models.Model):
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="face_images")
    image = models.FileField(upload_to="face_images/%Y/%m/%d")
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("student", "image"),
                name="unique_student_face_image",
            )
        ]
