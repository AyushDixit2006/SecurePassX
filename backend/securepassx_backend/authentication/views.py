from django.shortcuts import render
from .models import BlockedUser

import json
import numpy as np
import cv2

import hashlib
import secrets

from django.db import transaction
from .models import FaceAuthorization, FaceSecurityState


from rest_framework_simplejwt.exceptions import TokenError

from .utils import is_disposable_email

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import User, OTP, FaceData
from .utils import generate_otp, decode_base64_image, send_otp_email

from ai_module.face_engine import (
    get_face_encoding,
    compare_faces,
    is_real_face,
    has_face_movement,
)

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
@api_view(["POST"])
def send_otp(request):

    email = request.data.get("email")
    purpose = request.data.get("purpose")

    if not email or not isinstance(email, str):
        return Response(
            {"error": "Valid email is required"},
            status=400
        )

    email = email.strip()

    allowed_purposes = {"register", "login", "face_recovery"}

    if purpose not in allowed_purposes:
        return Response(
            {"error": "Invalid OTP purpose"},
            status=400
        )

    if is_disposable_email(email):
        return Response(
            {"error": "Disposable email not allowed"},
            status=400
        )

    user = User.objects.filter(email__iexact=email).first()
    user_exists = user is not None

    if purpose == "register" and user_exists:
        return Response(
            {"error": "This email is already registered. Please login instead."},
            status=400
        )

    if purpose in {"login", "face_recovery"} and not user_exists:
        return Response(
            {"error": "Email not registered. Please register first."},
            status=400
        )

    # Independent OTP block: does not block face login.
    blocked = BlockedUser.objects.filter(email__iexact=email).first()

    if blocked and blocked.blocked_until > timezone.now():
        return Response(
            {"error": "You are blocked. Try again after 1 hour"},
            status=429
        )

    now = timezone.now()

    # Remove expired OTPs.
    OTP.objects.filter(
        created_at__lt=now - timedelta(minutes=5)
    ).delete()

    # Replace the previous OTP for this email.
    OTP.objects.filter(email__iexact=email).delete()

    otp = generate_otp()

    OTP.objects.create(
        email=email,
        otp=otp,
        attempts=0,
        purpose=purpose
    )

    try:
        send_otp_email(email, otp)
    except Exception:
        OTP.objects.filter(
            email__iexact=email,
            purpose=purpose
        ).delete()

        return Response(
            {"error": "Unable to send OTP. Please try again."},
            status=503
        )

    return Response(
        {"message": "OTP sent to your email"},
        status=200
    )


# =====================
# STEP 2 : VERIFY OTP
# =====================
@api_view(["POST"])
@transaction.atomic
def verify_otp(request):

    email = request.data.get("email")
    otp = request.data.get("otp")
    purpose = request.data.get("purpose")

    if not email or not otp or not purpose:
        return Response(
            {"error": "Email, OTP and purpose are required"},
            status=400
        )

    if not isinstance(email, str) or not isinstance(otp, str):
        return Response(
            {"error": "Invalid verification request"},
            status=400
        )

    email = email.strip()

    if purpose not in {"register", "face_recovery"}:
        return Response(
            {"error": "This OTP purpose cannot use this verification endpoint"},
            status=400
        )

    now = timezone.now()

    # Check OTP block independently.
    blocked = BlockedUser.objects.filter(email__iexact=email).first()

    if blocked and blocked.blocked_until > now:
        return Response(
            {"error": "Try again after 1 hour"},
            status=429
        )

    record = (
        OTP.objects
        .select_for_update()
        .filter(
            email__iexact=email,
            purpose=purpose
        )
        .order_by("-created_at")
        .first()
    )

    if not record:
        return Response(
            {"error": "OTP not found or purpose mismatch"},
            status=400
        )

    if record.created_at < now - timedelta(minutes=5):
        record.delete()
        return Response(
            {"error": "OTP expired"},
            status=400
        )

    if not secrets.compare_digest(record.otp, otp):

        record.attempts += 1
        record.save(update_fields=["attempts"])

        if record.attempts >= 5:

            BlockedUser.objects.update_or_create(
                email=email,
                defaults={
                    "blocked_until": now + timedelta(hours=1)
                }
            )

            record.delete()

            return Response(
                {"error": "Too many attempts. Try after 1 hour"},
                status=429
            )

        return Response(
            {
                "error": (
                    f"Invalid OTP. Attempts left: "
                    f"{5 - record.attempts}"
                )
            },
            status=400
        )

    # Verify that the requested operation is still valid.
    user = User.objects.filter(email__iexact=email).first()

    if purpose == "register" and user:
        return Response(
            {"error": "Account already registered. Please login."},
            status=400
        )

    if purpose == "face_recovery" and not user:
        return Response(
            {"error": "User not found"},
            status=404
        )

    # Create the user only after successful registration OTP.
    if purpose == "register":
        user = User.objects.create(email=email)

    # Generate a separate one-time authorization.
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    authorization_purpose = (
        "register_face"
        if purpose == "register"
        else "recover_face"
    )

    with transaction.atomic():

        FaceAuthorization.objects.filter(
            user=user,
            purpose=authorization_purpose,
            used_at__isnull=True
        ).delete()

        FaceAuthorization.objects.create(
            user=user,
            purpose=authorization_purpose,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=5)
        )

        record.delete()

    return Response(
        {
            "message": "OTP verified",
            "user_id": user.id,
            "authorization_token": raw_token,
            "authorization_expires_in": 300
        },
        status=200
    )




# ===========================
# STEP 3: FACE REGISTRATION
# ===========================
@api_view(["POST"])
@transaction.atomic
def face_register(request):

    email = request.data.get("email")
    images = request.data.get("images")
    raw_token = request.data.get("authorization_token")

    if not isinstance(email, str) or not isinstance(raw_token, str):
        return Response(
            {"error": "Email and authorization token are required."},
            status=400
        )

    email = email.strip()

    if not email or not isinstance(images, list) or not 3 <= len(images) <= 10:
        return Response(
            {"error": "Provide between 3 and 10 images."},
            status=400
        )

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        return Response({"error": "User not found."}, status=404)

    # Initial registration must not overwrite existing face data.
    if FaceData.objects.filter(user=user).exists():
        return Response(
            {"error": "Face is already registered. Use face recovery instead."},
            status=409
        )

    # Process and validate images before consuming authorization.
    encodings = []

    for img_str in images:
        try:
            if not isinstance(img_str, str):
                continue

            img = decode_base64_image(img_str)

            if img is None:
                continue

            # Preserve existing soft liveness behavior.
            if not is_real_face(img):
                print("Weak liveness signal during registration.")

            encoding = get_face_encoding(img)

            if encoding is not None:
                encodings.append(encoding)

        except (ValueError, TypeError, cv2.error):
            continue

    if len(encodings) < 2:
        return Response(
            {"error": "Face not clear. Try again in better lighting."},
            status=400
        )

    variation = sum(
        np.linalg.norm(encodings[i] - encodings[i + 1])
        for i in range(len(encodings) - 1)
    )

    if variation < 0.35:
        return Response(
            {"error": "Please move your face slightly."},
            status=400
        )

    # Hash the raw authorization token before database lookup.
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = timezone.now()

    authorization = (
        FaceAuthorization.objects
        .select_for_update()
        .filter(
            user=user,
            purpose="register_face",
            token_hash=token_hash,
            used_at__isnull=True,
            expires_at__gt=now
        )
        .first()
    )

    if not authorization:
        return Response(
            {"error": "Invalid, expired, or already-used authorization."},
            status=403
        )

    # Check again inside the transaction before inserting records.
    if FaceData.objects.filter(user=user).exists():
        return Response(
            {"error": "Face is already registered."},
            status=409
        )

    FaceData.objects.bulk_create([
        FaceData(
            user=user,
            encoding=json.dumps(enc.tolist())
        )
        for enc in encodings
    ])

    # Consume the authorization only after successful face registration.
    authorization.used_at = now
    authorization.save(update_fields=["used_at"])

    return Response(
        {"message": "Face registered successfully."},
        status=200
    )




# =====================================
# LOGIN WITH OTP
# =====================================
@api_view(["POST"])
@transaction.atomic
def login_with_otp(request):

    email = request.data.get("email")
    otp = request.data.get("otp")

    if not email or not otp:
        return Response(
            {"error": "Email and OTP required"},
            status=400
        )

    if not isinstance(email, str) or not isinstance(otp, str):
        return Response(
            {"error": "Invalid login request"},
            status=400
        )

    email = email.strip()
    now = timezone.now()

    # Check the independent OTP block.
    blocked = BlockedUser.objects.filter(
        email__iexact=email
    ).first()

    if blocked and blocked.blocked_until > now:
        return Response(
            {"error": "You are blocked. Try again after 1 hour"},
            status=429
        )

    # Only login-purpose OTPs can authenticate.
    record = (
        OTP.objects
        .select_for_update()
        .filter(
            email__iexact=email,
            purpose="login"
        )
        .order_by("-created_at")
        .first()
    )

    if not record:
        return Response(
            {"error": "Login OTP not found or purpose mismatch"},
            status=400
        )

    if record.created_at < now - timedelta(minutes=5):
        record.delete()
        return Response(
            {"error": "OTP expired"},
            status=400
        )

    if not secrets.compare_digest(record.otp, otp):

        record.attempts += 1
        record.save(update_fields=["attempts"])

        if record.attempts >= 5:

            BlockedUser.objects.update_or_create(
                email=email,
                defaults={
                    "blocked_until": now + timedelta(hours=1)
                }
            )

            record.delete()

            return Response(
                {"error": "Too many attempts. Try after 1 hour"},
                status=429
            )

        return Response(
            {
                "error": (
                    f"Invalid OTP. Attempts left: "
                    f"{5 - record.attempts}"
                )
            },
            status=400
        )

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        record.delete()
        return Response(
            {"error": "User not found. Please register first."},
            status=404
        )

    # Consume the OTP after successful verification.
    record.delete()

    log_login_activity(request, user, "OTP")
    tokens = get_tokens_for_user(user)

    return Response(
        {
            "message": "Login successful via OTP",
            "access": tokens["access"],
            "refresh": tokens["refresh"]
        },
        status=200
    )

        



# ================
# LOGIN WITH FACE
# ================
@api_view(["POST"])
@transaction.atomic
def login_with_face(request):

    email = request.data.get("email")
    images = request.data.get("images")

    if not isinstance(email, str) or not isinstance(images, list):
        return Response(
            {"error": "Invalid login request"},
            status=400
        )

    email = email.strip()

    if not email or len(images) < 3 or len(images) > 10:
        return Response(
            {"error": "Provide between 3 and 10 images"},
            status=400
        )

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        return Response({"error": "User not found"}, status=404)

    # Lock this user's independent face-security state.
    state, _ = FaceSecurityState.objects.get_or_create(user=user)
    state = FaceSecurityState.objects.select_for_update().get(user=user)

    now = timezone.now()

    # Check face-mismatch block only. OTP blocking remains independent.
    if state.blocked_until and state.blocked_until > now:
        remaining_seconds = int(
            (state.blocked_until - now).total_seconds()
        ) + 1

        return Response({
            "error": "Face login temporarily blocked. Please try again later.",
            "blocked": True,
            "remaining_seconds": remaining_seconds,
            "allow_otp_login": True
        }, status=429)

    # Reset an expired face-mismatch block.
    if state.blocked_until and state.blocked_until <= now:
        state.failed_attempts = 0
        state.blocked_until = None

        state.save(update_fields=[
            "failed_attempts",
            "blocked_until",
            "updated_at"
        ])

    stored_faces = list(FaceData.objects.filter(user=user))

    if not stored_faces:
        return Response(
            {"error": "Face not registered"},
            status=400
        )

    valid_encodings = []
    valid_frames = []

    # Decode and process the captured frames once.
    for img_str in images:
        try:
            if not isinstance(img_str, str):
                continue

            img = decode_base64_image(img_str)

            if img is None:
                continue

            # Retain the same frames for the later liveness check.
            encoding = get_face_encoding(img)

            if encoding is not None:
                valid_encodings.append(encoding)
                valid_frames.append(img)

        except (ValueError, TypeError, cv2.error):
            continue

    if len(valid_encodings) < 2:
        return Response(
            {"error": "Face not clear. Try again in better lighting."},
            status=400
        )

    # STEP 1: Match identity before checking liveness.
    matched = False

    for unknown_encoding in valid_encodings:
        for face in stored_faces:
            try:
                known_encoding = np.array(json.loads(face.encoding))

                if compare_faces(known_encoding, unknown_encoding):
                    matched = True
                    break

            except (ValueError, TypeError):
                continue

        if matched:
            break

    # Genuine face mismatch: increment only the mismatch counter.
    if not matched:
        state.failed_attempts += 1
        state.last_failed_at = now

        if state.failed_attempts >= 3:
            state.blocked_until = now + timedelta(minutes=15)

            state.save(update_fields=[
                "failed_attempts",
                "blocked_until",
                "last_failed_at",
                "updated_at"
            ])

            return Response({
                "error": "Face login blocked for 15 minutes.",
                "blocked": True,
                "remaining_seconds": 900,
                "failed_attempts": state.failed_attempts,
                "allow_otp_login": True,
                "allow_face_update": False
            }, status=429)

        state.save(update_fields=[
            "failed_attempts",
            "last_failed_at",
            "updated_at"
        ])

        return Response({
            "error": "Face mismatch",
            "failed_attempts": state.failed_attempts,
            "attempts_remaining": 3 - state.failed_attempts,
            "allow_face_update": False
        }, status=401)

    # Identity matched: reset consecutive mismatch failures.
    state.failed_attempts = 0
    state.blocked_until = None
    state.last_failed_at = None

    # STEP 2: Check movement using the same captured frames.
    if not has_face_movement(valid_frames):
        state.liveness_failed_attempts += 1
        state.last_liveness_failed_at = now

        state.save(update_fields=[
            "failed_attempts",
            "blocked_until",
            "last_failed_at",
            "liveness_failed_attempts",
            "last_liveness_failed_at",
            "updated_at"
        ])

        recovery_required = state.liveness_failed_attempts >= 3

        return Response({
            "error": (
                "Movement not sufficient. Email OTP recovery is required."
                if recovery_required
                else "Please move your face slightly and try again."
            ),
            "liveness_failed_attempts": state.liveness_failed_attempts,
            "attempts_remaining": max(
                0, 3 - state.liveness_failed_attempts
            ),
            "recovery_required": recovery_required,
            "allow_face_update": False
        }, status=403 if recovery_required else 400)

    # STEP 3: Both identity and liveness passed.
    state.liveness_failed_attempts = 0
    state.last_liveness_failed_at = None

    state.save(update_fields=[
        "failed_attempts",
        "blocked_until",
        "last_failed_at",
        "liveness_failed_attempts",
        "last_liveness_failed_at",
        "updated_at"
    ])

    log_login_activity(request, user, "FACE")

    tokens = get_tokens_for_user(user)

    return Response({
        "message": "Face login successful",
        "access": tokens["access"],
        "refresh": tokens["refresh"]
    }, status=200)




# ==============
# UPDATE FACE
# ==============
@api_view(["POST"])
@transaction.atomic
def update_face(request):

    email = request.data.get("email")
    images = request.data.get("images")
    raw_token = request.data.get("authorization_token")

    if not isinstance(email, str) or not isinstance(raw_token, str):
        return Response(
            {"error": "Email and authorization token are required."},
            status=400
        )

    email = email.strip()

    if not email or not isinstance(images, list) or not 3 <= len(images) <= 10:
        return Response(
            {"error": "Provide between 3 and 10 images."},
            status=400
        )

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        return Response({"error": "User not found."}, status=404)

    # Face recovery is only for users with an existing face registration.
    if not FaceData.objects.filter(user=user).exists():
        return Response(
            {"error": "No registered face found. Complete initial registration first."},
            status=404
        )

    encodings = []
    valid_frames = []

    # Verify and lock the one-time face-recovery authorization
    # before performing expensive image processing.
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = timezone.now()

    authorization = (
        FaceAuthorization.objects
        .select_for_update()
        .filter(
            user=user,
            purpose="recover_face",
            token_hash=token_hash,
            used_at__isnull=True,
            expires_at__gt=now
        )
        .first()
    )

    if not authorization:
        return Response(
            {"error": "Invalid, expired, or already-used authorization."},
            status=403
        )

    # Validate and process new face images first.
    for img_str in images:

        try:
            if not isinstance(img_str, str):
                continue

            img = decode_base64_image(img_str)

            if img is None:
                continue

            # Preserve existing soft liveness behavior.
            if not is_real_face(img):
                print("Weak liveness signal during face recovery.")

            encoding = get_face_encoding(img)

            if encoding is not None:
                encodings.append(encoding)
                valid_frames.append(img)

        except (ValueError, TypeError, cv2.error):
            continue

    if len(encodings) < 2:
        return Response(
            {"error": "Face not clear. Try again in better lighting."},
            status=400
        )

        # Preserve existing movement threshold.
        # Validate basic face movement using landmarks from the same frames.
        # Validate basic face movement using facial landmarks.
    if not has_face_movement(valid_frames):
        return Response(
            {"error": "Please move your face slightly and try again."},
            status=400
        )

    # Replace existing face records only after all validation succeeds.
    FaceData.objects.filter(user=user).delete()

    FaceData.objects.bulk_create([
        FaceData(
            user=user,
            encoding=json.dumps(enc.tolist())
        )
        for enc in encodings
    ])

    # Consume authorization in the same database transaction.
    authorization.used_at = now
    authorization.save(update_fields=["used_at"])

    # Reset face-login security state after successful recovery.
    FaceSecurityState.objects.filter(user=user).update(
        failed_attempts=0,
        blocked_until=None,
        last_failed_at=None,
        liveness_failed_attempts=0,
        last_liveness_failed_at=None
    )

    return Response(
        {"message": "Face updated successfully."},
        status=200
    )



# =====================================
# LOGIN HISTORY API (FINAL WORKING)
# =====================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def login_history(request):

    django_user = request.user

    if not django_user or not django_user.is_authenticated:
        return Response(
            {"error": "Authentication required."},
            status=401
        )

    try:
        securepassx_user = User.objects.get(email=django_user.username)
    except User.DoesNotExist:
        return Response(
            {"error": "SecurePassX account not found."},
            status=404
        )

    logs = (
        LoginActivity.objects
        .filter(user=securepassx_user)
        .order_by("-created_at")[:10]
    )

    data = [
        {
            "email": log.email,
            "ip": log.ip_address,
            "device": log.device,
            "method": log.login_method,
            "time": log.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for log in logs
    ]

    return Response({"history": data})




# =====================================
# CHECK FACE LOGIN BLOCK STATUS
# =====================================
@api_view(["POST"])
def check_block(request):
    email = request.data.get("email")

    if not email or not isinstance(email, str):
        return Response(
            {"blocked": False},
            status=400
        )

    email = email.strip()

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        return Response({"blocked": False})

    state = FaceSecurityState.objects.filter(user=user).first()

    if not state:
        return Response({"blocked": False})

    now = timezone.now()

    if state.blocked_until and state.blocked_until > now:
        remaining_seconds = int(
            (state.blocked_until - now).total_seconds()
        ) + 1

        return Response({
            "blocked": True,
            "remaining_seconds": remaining_seconds,
            "message": "Face login temporarily blocked."
        })

    return Response({
        "blocked": False,
        "remaining_seconds": 0
    })



# ===============
#   Real Logout
# ===============


@api_view(["POST"])
def logout_view(request):
    refresh_token = request.data.get("refresh")

    if not refresh_token or not isinstance(refresh_token, str):
        return Response(
            {"error": "Refresh token is required."},
            status=400
        )

    try:
        token = RefreshToken(refresh_token)
        token.blacklist()

        return Response(
            {"message": "Logged out successfully."},
            status=200
        )

    except TokenError:
        return Response(
            {"error": "Invalid or expired refresh token."},
            status=400
        )
