import pickle
from django.utils import timezone
from django.shortcuts import render
from django.conf import settings
from django.contrib import messages
import os
from .models import DailyAttendance, StudentFaceImage, UserProfile
import os
import cv2
import numpy as np
import shutil  # For cleanup
from django.shortcuts import render
from django.contrib import messages
from django.conf import settings
from django.db import transaction  # Important for atomicity
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from insightface.app import FaceAnalysis
from .models import UserProfile

MIN_FACE_IMAGES = 30
ROLL_NUMBER_PREFIX = "24AK1F"
ALLOWED_PERIODS = {"P1", "P2", "P3"}


def next_roll_number():
    numbers = []
    for roll_number in UserProfile.objects.values_list("roll_number", flat=True):
        if roll_number and roll_number.startswith(ROLL_NUMBER_PREFIX):
            try:
                numbers.append(int(roll_number[len(ROLL_NUMBER_PREFIX):]))
            except ValueError:
                continue
    next_number = max(numbers, default=0) + 1
    return f"{ROLL_NUMBER_PREFIX}{next_number:04d}"

# ==========================================
# LOAD ARCFACE MODEL (ONCE)
# ==========================================
face_app = FaceAnalysis(name="buffalo_l")
face_app.prepare(ctx_id=0, det_size=(640, 640))

EMBEDDING_DIR = os.path.join(settings.BASE_DIR, "embeddings")
os.makedirs(EMBEDDING_DIR, exist_ok=True)


# ==========================================
# STUDENT REGISTRATION (SAFE VERSION)
# ==========================================
def student_register(request):
    if request.method == "POST":
        # Temporary storage for cleanup
        created_user = None
        image_dir = None
        saved_face_images = []

        try:
            name = request.POST.get("name")
            loginid = request.POST.get("loginid")
            email = request.POST.get("email")
            mobile = request.POST.get("mobile")
            password = request.POST.get("password")
            images = request.FILES.getlist("images")

            if request.POST.get("details_only") == "1":
                if not all([name, loginid, email, mobile, password]):
                    return JsonResponse({"error": "All fields are required."}, status=400)
                if not mobile.isdigit() or len(mobile) != 10:
                    return JsonResponse({"error": "Mobile number must contain exactly 10 digits."}, status=400)
                try:
                    validate_email(email)
                except ValidationError:
                    return JsonResponse({"error": "Enter a valid email address."}, status=400)
                if UserProfile.objects.filter(loginid=loginid).exists():
                    return JsonResponse({"error": "A user with this Login ID already exists."}, status=400)
                if UserProfile.objects.filter(email=email).exists():
                    return JsonResponse({"error": "A user with this email already exists."}, status=400)

                request.session["pending_registration"] = {
                    "name": name,
                    "loginid": loginid,
                    "email": email,
                    "mobile": mobile,
                    "password": password,
                }
                return JsonResponse({"details_saved": True})

            pending = request.session.get("pending_registration")
            if pending:
                name = pending["name"]
                loginid = pending["loginid"]
                email = pending["email"]
                mobile = pending["mobile"]
                password = pending["password"]

            # -------------------------------
            # BASIC VALIDATION
            # -------------------------------
            if not pending and not all([name, loginid, email, mobile, password]):
                return JsonResponse({"error": "All fields are required."}, status=400)

            if not mobile.isdigit() or len(mobile) != 10:
                return JsonResponse({"error": "Mobile number must contain exactly 10 digits."}, status=400)

            try:
                validate_email(email)
            except ValidationError:
                return JsonResponse({"error": "Enter a valid email address."}, status=400)

            if len(images) < MIN_FACE_IMAGES:
                return JsonResponse({"error": f"Please capture at least {MIN_FACE_IMAGES} face images."}, status=400)

            embedding_path = os.path.join(EMBEDDING_DIR, f"{loginid}.npy")

            # Check if user already exists
            if UserProfile.objects.filter(loginid=loginid).exists():
                return JsonResponse({"error": "A user with this Login ID already exists."}, status=400)

            if UserProfile.objects.filter(email=email).exists():
                return JsonResponse({"error": "A user with this email already exists."}, status=400)

            embeddings = []

            valid_images = []
            for image_file in images:
                image_bytes = image_file.read()
                img = cv2.imdecode(
                    np.frombuffer(image_bytes, np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if img is None:
                    continue

                faces = face_app.get(img)
                if not faces:
                    continue

                face = max(
                    faces,
                    key=lambda item: (item.bbox[2] - item.bbox[0]) * (item.bbox[3] - item.bbox[1])
                )
                embeddings.append(face.embedding)
                valid_images.append(image_bytes)

            # -------------------------------
            # FINAL VALIDATION: Face detection
            # -------------------------------
            if len(valid_images) < MIN_FACE_IMAGES:
                raise ValidationError(
                    f"Only {len(valid_images)} valid face images were received. "
                    f"Please capture all {MIN_FACE_IMAGES} images with your face visible."
                )

            mean_embedding = np.mean(embeddings, axis=0)

            # -------------------------------
            # DATABASE TRANSACTION (Atomic)
            # -------------------------------
            with transaction.atomic():
                # Create user inside transaction
                created_user = UserProfile.objects.create(
                    name=name,
                    loginid=loginid,
                    roll_number=next_roll_number(),
                    email=email,
                    mobile=mobile,
                    password=password  # ⚠️ Remember to hash in production!
                )

                for index, image_bytes in enumerate(valid_images, 1):
                    face_image = StudentFaceImage.objects.create(
                        student=created_user,
                        image=ContentFile(image_bytes, name=f"{loginid}/face_{index:02d}.jpg"),
                    )
                    saved_face_images.append(face_image)

                np.save(embedding_path, mean_embedding)

            # If we reach here → Everything succeeded
            KNOWN_FACES[loginid] = mean_embedding
            request.session.pop("pending_registration", None)
            return JsonResponse({
                "success": True,
                "message": "Registration successful. Face data is ready for attendance."
            })

        except Exception as e:
            # -------------------------------
            # CLEANUP ON ANY ERROR
            # -------------------------------
            error_msg = str(e) or "An unexpected error occurred during registration."
            if not error_msg.strip():  # In case e is empty
                error_msg = "Registration failed due to invalid data or processing error."

            # Delete database entry if it was created
            if created_user:
                try:
                    created_user.delete()
                except:
                    pass  # Best effort

            # Delete uploaded images folder
            if image_dir and os.path.exists(image_dir):
                try:
                    shutil.rmtree(image_dir)
                except:
                    pass

            for face_image in saved_face_images:
                try:
                    face_image.image.delete(save=False)
                except Exception:
                    pass

            # Delete embedding file if it was somehow saved
            embedding_path = os.path.join(EMBEDDING_DIR, f"{loginid}.npy") if loginid else None
            if embedding_path and os.path.exists(embedding_path):
                try:
                    os.remove(embedding_path)
                except:
                    pass

            return JsonResponse({"error": f"Registration failed: {error_msg}"}, status=400)

    # GET request
    return render(request, "studentRegister.html")


def validate_registration_face(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request."}, status=400)

    try:
        data = json.loads(request.body)
        image_data = data.get("image", "")
        _, encoded = image_data.split(",", 1)
        frame = cv2.imdecode(
            np.frombuffer(base64.b64decode(encoded), np.uint8),
            cv2.IMREAD_COLOR,
        )
        if frame is None:
            return JsonResponse({"face_detected": False})
        return JsonResponse({"face_detected": bool(face_app.get(frame))})
    except Exception:
        return JsonResponse({"face_detected": False})


from datetime import time, datetime

# EXACTLY FROM YOUR IMAGE
TIME_SLOTS = [
    ("P1", time(9, 30),  time(9, 35)),
    ("P2", time(10, 45), time(10, 50)),
    ("P3", time(12, 0), time(13, 30)),
]

def get_current_period():
    now = timezone.localtime().time()
    for period, start, end in TIME_SLOTS:
        if start <= now <= end:
            return period
    return None



import os
import json
import base64
import logging
import csv
import numpy as np
import cv2

from datetime import date, datetime, time
from django.http import JsonResponse, StreamingHttpResponse
from django.conf import settings

from insightface.app import FaceAnalysis
from .models import DailyAttendance

logger = logging.getLogger(__name__)

# =====================================================
# CONFIG
# =====================================================
EMBEDDING_DIR = os.path.join(settings.BASE_DIR, "embeddings")
THRESHOLD = 0.45
live_cap = None

# =====================================================
# TIMETABLE (FROM YOUR IMAGE)
# =====================================================
TIME_SLOTS = [
    ("P1", time(9, 30),  time(9, 35)),
    ("P2", time(10, 45), time(10, 50)),
    ("P3", time(12, 0), time(13, 30)),
]

def get_current_period():
    now = timezone.localtime().time()
    for period, start, end in TIME_SLOTS:
        if start <= now <= end:
            return period
    return None

# =====================================================
# LOAD ARCFACE MODEL
# =====================================================
face_app = FaceAnalysis(name="buffalo_l")
face_app.prepare(ctx_id=0, det_size=(640, 640))

# =====================================================
# LOAD REGISTERED EMBEDDINGS
# =====================================================
def load_known_faces():
    known = {}
    if not os.path.exists(EMBEDDING_DIR):
        return known

    for file in os.listdir(EMBEDDING_DIR):
        if file.endswith(".npy"):
            student_id = file.replace(".npy", "")
            known[student_id] = np.load(
                os.path.join(EMBEDDING_DIR, file)
            )
    return known

KNOWN_FACES = load_known_faces()

# =====================================================
# COSINE DISTANCE
# =====================================================
def cosine_distance(a, b):
    return 1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# =====================================================
# CAMERA INIT
# =====================================================
def init_live_capture():
    global live_cap
    if live_cap is None or not live_cap.isOpened():
        live_cap = cv2.VideoCapture(0)
        if not live_cap.isOpened():
            logger.error("❌ Camera not accessible")
            live_cap = None

def ensure_daily_attendance(date_value):
    for student in UserProfile.objects.all().only("loginid", "name", "roll_number"):
        DailyAttendance.objects.get_or_create(
            student_id=student.loginid,
            date=date_value,
            defaults={
                "roll_number": student.roll_number or "",
                "student_name": student.name,
            },
        )


def mark_daily_attendance(student_id, period, date_value):
    student = UserProfile.objects.filter(loginid=student_id).only("name", "roll_number").first()
    if not student or period not in ALLOWED_PERIODS:
        return None, False

    attendance, created = DailyAttendance.objects.get_or_create(
        student_id=student_id,
        date=date_value,
        defaults={
            "roll_number": student.roll_number or "",
            "student_name": student.name,
        },
    )
    period_field = f"period_{period[1:]}"
    changed = getattr(attendance, period_field) != "Present"
    setattr(attendance, period_field, "Present")
    if attendance.status != "Present":
        attendance.status = "Present"
        changed = True
    if attendance.attendance_time is None:
        attendance.attendance_time = timezone.now()
        changed = True
    if changed:
        attendance.save()
    return attendance, created or changed

# =====================================================
# 🎥 REALTIME STREAM (HOURLY ATTENDANCE)
# =====================================================
def realtime(request):

    def generate_frames():
        init_live_capture()
        today = timezone.localdate()

        while True:
            success, frame = live_cap.read()
            if not success:
                break

            period = get_current_period()
            faces = face_app.get(frame)

            for face in faces:
                emb = face.embedding
                bbox = face.bbox.astype(int)

                name = "Unknown"
                min_dist = 1.0

                for sid, ref_emb in KNOWN_FACES.items():
                    dist = cosine_distance(emb, ref_emb)
                    if dist < min_dist:
                        min_dist = dist
                        name = sid

                if min_dist < THRESHOLD and period:
                    mark_daily_attendance(name, period, today)

                color = (0,255,0) if min_dist < THRESHOLD else (0,0,255)

                cv2.rectangle(frame, bbox[:2], bbox[2:], color, 2)
                cv2.putText(
                    frame,
                    f"{name} | {period}",
                    (bbox[0], bbox[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color,
                    2
                )

            _, buffer = cv2.imencode(".jpg", frame)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                buffer.tobytes() +
                b"\r\n"
            )

        if live_cap:
            live_cap.release()

    return StreamingHttpResponse(
        generate_frames(),
        content_type="multipart/x-mixed-replace; boundary=frame"
    )

# =====================================================
# 📸 AUTO ATTENDANCE (BASE64 | HOURLY)
# =====================================================
def auto_attendance(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        global KNOWN_FACES
        KNOWN_FACES = load_known_faces()
        data = json.loads(request.body)
        image_data = data.get("image")

        if not image_data:
            return JsonResponse({"error": "No image"}, status=400)

        _, encoded = image_data.split(",", 1)
        frame = cv2.imdecode(
            np.frombuffer(base64.b64decode(encoded), np.uint8),
            cv2.IMREAD_COLOR
        )

        period = get_current_period()
        today = timezone.localdate()
        print(today, period)

        ensure_daily_attendance(today)

        if period is None:
            return JsonResponse({
                "period": None,
                "faces_detected": 0,
                "message": "Attendance is available only during a scheduled class period."
            })

        faces = face_app.get(frame)
        results = []

        for face in faces:
            emb = face.embedding
            min_dist = 1.0
            student_id = None

            for sid, ref_emb in KNOWN_FACES.items():
                dist = cosine_distance(emb, ref_emb)
                if dist < min_dist:
                    min_dist = dist
                    student_id = sid

            if student_id and min_dist < THRESHOLD and period:
                attendance, created = mark_daily_attendance(student_id, period, today)

                results.append({
                    "student_id": str(student_id),
                    "period": str(period),
                    "confidence": float(round(1 - float(min_dist), 2)),
                    "status": "Marked" if created else "Already Marked"
                })

        return JsonResponse({
            "period": str(period),
            "faces_detected": len(results),
            "results": results
        })

    except Exception:
        logger.exception("❌ Auto attendance failed")
        return JsonResponse({"error": "Processing error"}, status=500)
