import random
import base64
import numpy as np
import cv2
import threading
import requests  

from django.conf import settings

from disposable_email_domains import blocklist


# ===============================
# GENERATE OTP
# ===============================

def generate_otp():
    return str(random.randint(100000, 999999))


# ===============================
# DECODE BASE64 IMAGE
# ===============================

def decode_base64_image(base64_string):

    if "," in base64_string:
        base64_string = base64_string.split(",")[1]

    img_bytes = base64.b64decode(base64_string)

    img_array = np.frombuffer(img_bytes, dtype=np.uint8)

    image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    return image


# ===============================
# ✅ DISPOSABLE EMAIL CHECK (NEW)
# ===============================

# ===============================
# 🔥 STRICT EMAIL WHITELIST
# ===============================

ALLOWED_EMAIL_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com"
}

def is_disposable_email(email):
    try:
        domain = email.split("@")[1].lower()

        # ❌ Block if not allowed
        if domain not in ALLOWED_EMAIL_DOMAINS:
            print("🚫 Blocked email domain:", domain)
            return True

        return False

    except Exception as e:
        print("❌ Email validation error:", e)
        return True


# ===============================
# SEND EMAIL IN BACKGROUND
# ===============================


def send_email_background(email, otp):
    try:

        text_content = f"Your OTP is {otp}. Valid for 5 minutes."

        relay_url = settings.EMAIL_RELAY_URL
        relay_secret = settings.EMAIL_RELAY_SECRET

        response = requests.post(
            relay_url,
            json={
                "secret": relay_secret,
                "email": email,
                "otp": otp,
                "purpose": "verification"
            },
            timeout=30,
            allow_redirects=False
        )

        if response.status_code == 302:
            redirect_url = response.headers.get("Location")

            if not redirect_url:
                raise Exception("Google relay returned no redirect URL")

            response = requests.get(
                redirect_url,
                timeout=30
            )

        response.raise_for_status()

        result = response.json()

        if not result.get("success"):
            raise Exception(result.get("message", "Email relay rejected request"))

        print(f"OTP email sent successfully to {email}")

    except Exception as exc:
        print("EMAIL RELAY ERROR TYPE:", type(exc).__name__)
        print("EMAIL RELAY ERROR DETAILS:", repr(exc))


# ===============================
# SEND OTP EMAIL (ASYNC)
# ===============================

def send_otp_email(email, otp):

    thread = threading.Thread(
        target=send_email_background,
        args=(email, otp)
    )

    thread.start()