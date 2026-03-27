from django.shortcuts import render
from .models import BlockedUser

import json
import numpy as np
import cv2

from .utils import is_disposable_email

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import User, OTP, FaceData
from .utils import generate_otp, decode_base64_image, send_otp_email

from ai_module.face_engine import get_face_encoding, compare_faces, is_real_face

from disposable_email_checker.validators import validate_disposable_email

from django.utils import timezone
from datetime import timedelta

from rest_framework_simplejwt.tokens import RefreshToken

from .models import LoginActivity

from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes

from django.contrib.auth.models import User as DjangoUser

from rest_framework_simplejwt.authentication import JWTAuthentication


# =====================
#      JWT HELPER 
# =====================
from django.contrib.auth.models import User as DjangoUser

def get_tokens_for_user(user):

    # 🔥 MAP CUSTOM USER → DJANGO USER
    django_user, _ = DjangoUser.objects.get_or_create(
        username=user.email
    )

    refresh = RefreshToken.for_user(django_user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


# =====================
#  ROLE CHECK HELPER
# =====================
def is_admin(user):
    return user.role == "admin"


# ======================
# LOGIN TRACKING HELPER
# ======================
def log_login_activity(request, user, method):

    ip = request.META.get('REMOTE_ADDR')

    device = request.META.get('HTTP_USER_AGENT', '')

    LoginActivity.objects.create(
        user=user,
        email=user.email,
        ip_address=ip,
        device=device,
        login_method=method
    )


# ===================
# STEP 1 : SEND OTP
# ===================
@api_view(['POST'])
def send_otp(request):

    email = request.data.get("email")
    BlockedUser.objects.filter(blocked_until__lt=timezone.now()).delete()
    purpose = request.data.get("purpose")  # 🔥 NEW (register / login)

    if not email:
        return Response({"error": "Email is required"})

    print("📩 Checking email:", email)
    print("🚫 Disposable check result:", is_disposable_email(email))

    # ✅ NEW DISPOSABLE EMAIL CHECK
    if is_disposable_email(email):
        return Response({"error": "Disposable email not allowed"}, status=400)
    

    OTP.objects.filter(
    created_at__lt=timezone.now() - timedelta(minutes=5)
    ).delete()


    # 🔥 EXISTING LOGIC (UNCHANGED)
    user_exists = User.objects.filter(email=email).exists()

    if purpose == "register" and user_exists:
        return Response({
            "error": "This email is already registered. Please login instead."
        })

    if purpose == "login" and not user_exists:
        return Response({
            "error": "Email not registered. Please register first."
        })
    
    # ======================
    # 🔥 BLOCK CHECK (NEW)
    # ======================
    blocked = BlockedUser.objects.filter(email=email).first()

    if blocked and blocked.blocked_until > timezone.now():
        return Response({"error": "You are blocked. Try again after 1 hour"})

    # ================= OTP CLEANUP =================
    OTP.objects.filter(
        email=email,
        created_at__lt=timezone.now() - timedelta(minutes=5)
    ).delete()

    OTP.objects.filter(email=email).delete()

    otp = generate_otp()

    OTP.objects.create(
        email=email,
        otp=otp,
        attempts=0,
    )

    send_otp_email(email, otp)

    return Response({"message": "OTP sent to your email"})

# =====================
# STEP 2 : VERIFY OTP
# =====================
@api_view(['POST'])
def verify_otp(request):

    email = request.data.get("email")
    otp = request.data.get("otp")

    if not email or not otp:
        return Response({"error": "Email and OTP required"})

    OTP.objects.filter(
        created_at__lt=timezone.now() - timedelta(minutes=5)
    ).delete()

    record = OTP.objects.filter(email=email).order_by("-created_at").first()

    if not record:
        return Response({"error": "OTP not found"})

    blocked = BlockedUser.objects.filter(email=email).first()

    if blocked and blocked.blocked_until > timezone.now():
        return Response({"error": "Try again after 1 hour"})

    if timezone.now() > record.created_at + timedelta(minutes=5):
        return Response({"error": "OTP expired"})

    if record.otp != otp:

        record.attempts += 1

        if record.attempts >= 5:
            BlockedUser.objects.update_or_create(
                email=email,
                defaults={
                    "blocked_until": timezone.now() + timedelta(hours=1)
                }
            )

            record.save()

            return Response({"error": "Too many attempts. Try after 1 hour"})

        record.save()
        return Response({"error": f"Invalid OTP. Attempts left: {5 - record.attempts}"})

    user, _ = User.objects.get_or_create(email=email)

    OTP.objects.filter(email=email).delete()

    return Response({"message": "OTP verified", "user_id": user.id})


# ===========================
# STEP 3 : FACE REGISTRATION 
# ===========================
@api_view(['POST'])
def face_register(request):

    email = request.data.get("email")
    images = request.data.get("images")

    if not email or not images or len(images) < 3:
        return Response({"error": "Provide at least 3 images"})

    user = User.objects.filter(email=email).first()

    if not user:
        return Response({"error": "User not found"})

    encodings = []

    for img_str in images:

        img = decode_base64_image(img_str)

        # 🔥 SOFT LIVENESS CHECK (NO HARD REJECTION)
        if not is_real_face(img):
            print("⚠️ Weak liveness signal, continuing...")

        encoding = get_face_encoding(img)

        if encoding is None:
            print("⚠️ Face not detected in one frame")
            continue   # 🔥 SKIP INSTEAD OF FAIL

        encodings.append(encoding)

    # 🔥 MINIMUM VALID FRAMES CHECK
    if len(encodings) < 2:
        return Response({"error": "Face not clear. Try again in better lighting"})

    # 🔥 RELAXED MOVEMENT CHECK
    variation = 0
    for i in range(len(encodings) - 1):
        variation += np.linalg.norm(encodings[i] - encodings[i+1])

    if variation < 0.35:
        return Response({"error": "Please move your face slightly"})

    # SAVE FACE
    FaceData.objects.filter(user=user).delete()

    for enc in encodings:
        FaceData.objects.create(
            user=user,
            encoding=json.dumps(enc.tolist())
        )

    return Response({"message": "Face registered successfully"})


# =====================================
# LOGIN WITH OTP (FINAL FIXED)
# =====================================
@api_view(['POST'])
def login_with_otp(request):

    email = request.data.get("email")
    otp = request.data.get("otp")

    if not email or not otp:
        return Response({"error": "Email and OTP required"})

    # 🔥 CLEAN OLD OTP
    OTP.objects.filter(
        created_at__lt=timezone.now() - timedelta(minutes=5)
    ).delete()

    # 🔥 GET LATEST OTP
    record = OTP.objects.filter(email=email).order_by("-created_at").first()

    if not record:
        return Response({"error": "OTP not found"})

    # 🔥 EXPIRY CHECK
    if record.created_at < timezone.now() - timedelta(minutes=5):
        return Response({"error": "OTP expired"})

    # 🔥 WRONG OTP
    if record.otp != otp:

        record.attempts += 1

        if record.attempts >= 5:

            from .models import BlockedUser

            BlockedUser.objects.update_or_create(
                email=email,
                defaults={
                    "blocked_until": timezone.now() + timedelta(hours=1)
                }
            )

            record.save()

            return Response({"error": "Too many attempts. Try after 1 hour"})

        record.save()

        return Response({
            "error": f"Invalid OTP. Attempts left: {5 - record.attempts}"
        })

    # ✅ CORRECT OTP
    record.delete()

    user = User.objects.filter(email=email).first()

    # 🔥 LOGIN ACTIVITY (if exists)
    log_login_activity(request, user, "OTP")

    tokens = get_tokens_for_user(user)

    return Response({
        "message": "Login successful via OTP",
        "access": tokens["access"],
        "refresh": tokens["refresh"]
    })
        


# ================
# LOGIN WITH FACE 
# ================
@api_view(['POST'])
def login_with_face(request):

    email = request.data.get("email")
    images = request.data.get("images")

    if not email or not images or len(images) < 3:
        return Response({"error": "At least 3 images required"})

    user = User.objects.filter(email=email).first()

    BlockedUser.objects.filter(blocked_until__lt=timezone.now()).delete()

    # ==============
    #   BLOCK CHECK 
    # ==============
    blocked = BlockedUser.objects.filter(email=email).first()

    if blocked and blocked.blocked_until > timezone.now():
        return Response({"error": "You are blocked. Try again after 1 hour"})

    if not user:
        return Response({"error": "User not found"})

    stored_faces = FaceData.objects.filter(user=user)

    if not stored_faces.exists():
        return Response({"error": "Face not registered"})

    valid_encodings = []

    for img_str in images:

        img = decode_base64_image(img_str)

        # 🔥 SOFT LIVENESS CHECK
        if not is_real_face(img):
            print("⚠️ Weak liveness signal")

        encoding = get_face_encoding(img)

        if encoding is not None:
            valid_encodings.append(encoding)
        else:
            print("⚠️ Skipping bad frame")


    # =============================
    #  NEW: MINIMUM VALID FRAMES
    # =============================
    if len(valid_encodings) < 2:
        return Response({"error": "Face not clear. Try again in better lighting"})


    # =========================
    #  RELAXED MOVEMENT CHECK 
    # =========================
    variation = 0
    for i in range(len(valid_encodings) - 1):
        variation += np.linalg.norm(valid_encodings[i] - valid_encodings[i+1])

    if variation < 0.30:   # 🔥 slightly relaxed
        return Response({"error": "Please move your face slightly"})

    # 🔥 MATCHING (UNCHANGED LOGIC)
    for unknown_encoding in valid_encodings:

        for face in stored_faces:

            known_encoding = np.array(json.loads(face.encoding))

            if compare_faces(known_encoding, unknown_encoding):

                tokens = get_tokens_for_user(user)

                return Response({
                    "message": "Face login successful",
                    "access": tokens["access"],
                    "refresh": tokens["refresh"]
                })

    return Response({
        "error": "Face mismatch",
        "allow_face_update": True
    })


# ==============
# UPDATE FACE 
# ==============
@api_view(['POST'])
def update_face(request):

    email = request.data.get("email")
    images = request.data.get("images")

    if not email or not images or len(images) < 3:
        return Response({"error": "Provide at least 3 images"})

    user = User.objects.filter(email=email).first()

    if not user:
        return Response({"error": "User not found"})

    encodings = []

    for img_str in images:

        img = decode_base64_image(img_str)

        # 🔥 SOFT LIVENESS CHECK
        if not is_real_face(img):
            print("⚠️ Weak liveness signal, continuing...")

        encoding = get_face_encoding(img)

        if encoding is None:
            print("⚠️ Face not detected in one frame")
            continue

        encodings.append(encoding)

    # 🔥 MINIMUM FRAMES CHECK
    if len(encodings) < 2:
        return Response({"error": "Face not clear. Try again in better lighting"})

    # 🔥 SAME MOVEMENT LOGIC
    variation = 0
    for i in range(len(encodings) - 1):
        variation += np.linalg.norm(encodings[i] - encodings[i+1])

    if variation < 0.30:
        return Response({"error": "Please move your face slightly"})

    # 🔥 SAVE FACE
    FaceData.objects.filter(user=user).delete()

    for enc in encodings:
        FaceData.objects.create(
            user=user,
            encoding=json.dumps(enc.tolist())
        )

    return Response({"message": "Face updated successfully"})


# =====================================
# LOGIN HISTORY API (FINAL WORKING)
# =====================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def login_history(request):

    email = request.GET.get("email")

    print("EMAIL RECEIVED:", email)

    if not email:
        return Response({"history": []})

    logs = LoginActivity.objects.filter(email=email).order_by('-created_at')[:10]

    data = []

    for log in logs:
        data.append({
            "email": log.email,
            "ip": log.ip_address,
            "device": log.device,
            "method": log.login_method,
            "time": log.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    print("LOG COUNT:", len(data))

    return Response({"history": data})


# =====================================
# CHECK BLOCK STATUS
# =====================================
@api_view(['POST'])
def check_block(request):

    email = request.data.get("email")

    latest_otp = OTP.objects.filter(email=email).order_by("-created_at").first()

    if latest_otp and latest_otp.blocked_until and latest_otp.blocked_until > timezone.now():
        return Response({"blocked": True})

    return Response({"blocked": False})


# ===============
#   Real Logout
# ===============

@api_view(['POST'])
def logout_view(request):
    try:
        refresh_token = request.data.get("refresh")

        token = RefreshToken(refresh_token)
        token.blacklist()

        return Response({"message": "Logged out successfully"})
    except Exception:
        return Response({"error": "Invalid token"})