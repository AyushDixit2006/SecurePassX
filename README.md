# 🔐 SecurePassX — Passwordless Authentication System

SecurePassX is a modern authentication system that eliminates traditional passwords using:

✔ Email OTP Authentication
✔ Face Recognition Login
✔ Anti-Spoofing + Liveness Detection
✔ JWT-based Secure Sessions

---

## 🚀 Core Idea

A secure and scalable passwordless system designed to:

* Eliminate password dependency
* Prevent brute-force and credential attacks
* Enhance security using AI-based face verification
* Provide seamless and user-friendly authentication

---

## 🚀 Features

### 🔐 Authentication

* Email OTP-based registration & login
* Face recognition login
* Purpose-based OTP (`register` / `login`)
* JWT-based authentication (Access + Refresh tokens)

---

### 🛡️ Security Features

* OTP expiry (5 minutes)
* Maximum 5 OTP attempts
* Automatic user block for 1 hour after failed attempts
* Separate blocked user system (persistent blocking)
* Old OTP auto-deletion (database cleanup)
* Disposable email blocking (only trusted domains allowed)

---

### 🤖 Face Recognition & AI

* Multi-frame capture (3 frames)
* Liveness detection (movement-based)
* Anti-spoofing protection
* Multiple face encodings per user
* Face update system (after failed attempts)

---

### 🧠 Smart Logic

* Prevent duplicate registration
* Auto redirect to login if already registered
* Block login if user not registered
* Separate email input for OTP & Face login
* Face update option after multiple failures

---

## 🔐 JWT Authentication (Advanced Security)

* Access Token + Refresh Token system
* Protected APIs using `IsAuthenticated`
* Frontend route protection
* Token auto-refresh (no login interruption)
* Real logout using token blacklisting
* Secure session management

---

## 💻 Frontend Features

### 🎨 UI/UX

* Modern card-based UI
* Step-based registration flow
* Tab-based login (OTP / Face)
* Face scan animation
* Professional dashboard UI

---

### 🌗 Theme System

* Light / Dark mode toggle
* Theme saved in localStorage

---

### 📱 Responsiveness

* Works on Desktop
* Works on Android
* Mobile-friendly layout

---

### 🎥 Camera System

* Live camera preview
* Circular camera UI
* Scan animation starts/stops automatically
* Auto-stop camera after capture

---

### 🔢 OTP UX Improvements

* 6-digit OTP input boxes
* Auto-focus between inputs
* Paste support (auto-fill)
* Resend OTP timer (cooldown system)

---

### 🔁 Smart Redirect

* Email auto-filled via URL params
* Redirect to login if already registered

---

## 📊 Dashboard

* Authentication status (OTP + Face)
* Login activity tracking
* Device & IP detection
* Real-time activity display
* Secure logout system

---

## 🧩 Project Structure

SecurePassX
│
├── backend
│   └── securepassx_backend
│       ├── manage.py
│       ├── securepassx_backend
│       │   ├── settings.py
│       │   ├── urls.py
│       │   └── wsgi.py
│       └── authentication
│           ├── models.py
│           ├── serializers.py
│           ├── views.py
│           ├── urls.py
│           └── utils.py
│
├── ai_module
│   └── face_engine.py
│
├── frontend
│   ├── html
│   │    ├── login.html
│   │    ├── register.html
│   │    └── dashboard.html
│   │
│   ├── css
│   │    └── style.css
│   │
│   └── js
│       ├── login.js
│       ├── register.js
│       └── camera.js
│
└── requirements.txt

---

## ⚙️ Setup Instructions

### 1️⃣ Clone Repository

git clone https://github.com/AyushDixit2006/SecurePassX.git
cd SecurePassX

---

### 2️⃣ Create Virtual Environment

python -m venv venv

Activate:

Windows:
venv\Scripts\activate

Linux/Mac:
source venv/bin/activate

---

### 3️⃣ Install Dependencies

pip install -r requirements.txt

---

### 4️⃣ Email Configuration (IMPORTANT)

Create a `.env` file in root directory:

EMAIL_HOST_USER=[your_email@gmail.com](mailto:your_email@gmail.com)
EMAIL_HOST_PASSWORD=your_app_password

---

### 5️⃣ Update settings.py

Add:

import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

---

### ⚠️ Notes

* Use Gmail App Password (not normal password)
* Enable 2-step verification

---

### 6️⃣ Run Migrations

python manage.py makemigrations
python manage.py migrate

---

### 7️⃣ Run Server

python manage.py runserver

---

## 🌐 Access

Frontend:
http://127.0.0.1:8000/html/login.html

Backend API:
http://127.0.0.1:8000/api/auth

---

## ⚙️ Working Flow

### 🔐 Registration

1. Enter email
2. Receive OTP
3. Verify OTP
4. Register face (3 frames + liveness)

---

### 🔓 Login

OTP Login:
Enter email → OTP → Verify → Login

Face Login:
Enter email → Scan face → Verify → Login

---

## 🛡️ Security Flow

* OTP expires in 5 minutes

* Max 5 attempts allowed

* After 5 failed attempts → user blocked for 1 hour

* Blocking stored separately (not dependent on OTP)

* Face login includes:
  ✔ Liveness detection
  ✔ Multi-frame verification
  ✔ Anti-spoofing protection

---

## 📁 Ignored Files (.gitignore)

.env
db.sqlite3
media/
**pycache**/
*.pyc
venv/
.DS_Store
*.log

---

## 🧪 Tested Features

✔ OTP Registration & Login
✔ Face Registration
✔ Face Login
✔ OTP attempt limit & blocking
✔ JWT authentication & protection
✔ Dashboard activity display
✔ Disposable email blocking

---

## 🔒 Security Highlights

* Prevents brute-force OTP attacks
* Implements account blocking system
* Secure JWT session handling
* Face anti-spoofing with liveness detection
* Backend + frontend protection layers

---

## 🏆 Project Status

✅ Fully working backend
✅ Fully working frontend
✅ Modern UI
✅ Secure authentication system
✅ Hackathon-ready
