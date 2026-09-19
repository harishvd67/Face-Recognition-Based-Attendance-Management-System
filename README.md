# Face Recognition Based Attendance Management System

A Django application for student registration, browser-based face capture, face recognition, and period-wise attendance reporting.

## Features

- Student registration with email and mobile validation.
- Browser camera capture with face validation.
- InsightFace/ArcFace embeddings for recognition.
- Period-wise attendance stored in SQLite through Django migrations.
- Faculty attendance dashboard and day-wise CSV reports.

## Technologies

- Python 3.11 (recommended)
- Django 5.2
- SQLite
- OpenCV, NumPy, InsightFace, and ONNX Runtime
- HTML, CSS, and browser camera APIs

## Project structure

- `Students/`: student models, registration, face recognition, and attendance views.
- `Faculty/`: faculty dashboard and reports.
- `Templates/`: Django templates.
- `static/`: shared static assets.
- `media/`: runtime uploads; created as needed and intentionally ignored by Git.
- `embeddings/`: runtime face embeddings; generated during registration and intentionally ignored by Git.
- `models/`: legacy model artifacts retained for reference; the active recognition path uses InsightFace.

## Fresh installation on Windows

```powershell
py -3.11 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/.

Do not copy `db.sqlite3`, `media/`, `embeddings/`, or `attendance_log.json` from another computer. A fresh database is created by `migrate`.

## Face recognition setup and use

InsightFace downloads the `buffalo_l` model the first time a face feature is used and stores it in the user cache (normally `%USERPROFILE%\.insightface\models`). Internet access is required for that first download. The model is not bundled because it is a large external model artifact.

1. Open **Student Registration**.
2. Enter the student details and capture at least 30 clear images of one face.
3. Allow camera access in the browser and complete registration.
4. Open **Student Attendance** during one of the configured periods in `Students/views.py`.
5. Faculty can use the default legacy dashboard login `admin` / `admin` for local testing. Change this authentication before production use.

The camera used by the browser must be available to the browser. The optional `/live_stream/` endpoint uses a camera attached to the server machine.

## Configuration

- `DJANGO_SECRET_KEY`: set a unique secret outside local development.
- `DJANGO_ALLOWED_HOSTS`: comma-separated host names for deployment.
- `DJANGO_DB_PATH`: optional SQLite path; defaults to `db.sqlite3` in the project root.
- `DEBUG` is enabled for local development in `settings.py`. Set it to `False` for deployment and configure `ALLOWED_HOSTS`.
- `python manage.py collectstatic` writes deployment assets to `staticfiles/`.

## Common errors

**`no such table: Students_dailyattendance`**: the database was not migrated or is a stale copied database. Delete the local SQLite file only if its data is disposable, then run `python manage.py migrate`.

**InsightFace model download or import error**: install the requirements in the activated virtual environment and allow the first model download. CPU execution is selected by default; no CUDA installation is required.

**Camera is unavailable**: grant browser camera permission, use HTTPS when required by the browser, and make sure another application is not using the camera.

**`TemplateDoesNotExist` or missing CSS**: run commands from any directory after cloning; paths are based on `BASE_DIR`. Confirm that `static/css/styles.css` exists and run `collectstatic` for deployment.

## Files intentionally excluded from GitHub

- `db.sqlite3` and `*.sqlite3`
- `media/`
- `embeddings/*.npy`
- `attendance_log.json`
- `staticfiles/`
- Python caches, virtual environments, and `.env`

These files contain local database state, uploaded faces, attendance records, generated embeddings, or machine-specific runtime data.
