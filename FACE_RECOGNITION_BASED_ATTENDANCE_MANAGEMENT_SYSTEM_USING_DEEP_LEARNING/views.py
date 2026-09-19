

from django.shortcuts import render
from Students.models import DailyAttendance


def index(request):
    attendance_records = DailyAttendance.objects.order_by('-date', 'student_id')[:50]
    return render(request, 'index.html', {'attendance_records': attendance_records})


def studentRegister(request):
    return render(request,'studentRegister.html')


def facultyLogin(request):
    return render(request,'facultyLogin.html')


def studentLogin(request):
    return render(request,'studentAttendence.html')
