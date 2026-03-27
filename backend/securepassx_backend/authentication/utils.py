import random
import base64
import numpy as np
import cv2
import threading
import requests  

from django.core.mail import EmailMultiAlternatives
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
        subject = "SecurePassX Verification Code"

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:Arial, sans-serif;">
<div style="max-width:600px;margin:auto;padding:20px;">
<div style="background:#020617;border-radius:16px;padding:30px;border:1px solid #1e293b;box-shadow:0px 0px 20px rgba(0,0,0,0.5);">

<h2 style="text-align:center;color:#38bdf8;">🔐 SecurePassX</h2>
<p style="text-align:center;color:#64748b;">Passwordless Authentication System</p>

<h1 style="text-align:center;color:white;margin-top:30px;">Hello 👋</h1>

<p style="text-align:center;color:#cbd5f5;">
Use the OTP below to securely log in: 
</p>


<div style="
background:linear-gradient(90deg,#22c55e,#16a34a);
color:white;
text-align:center;
font-size:42px;
letter-spacing:8px;
padding:15px;
margin:30px 0;
border-radius:10px;
font-weight:bold;">
{otp}
</div>

<p style="text-align:center;color:#94a3b8;">
⏳ Valid for 5 minutes<br>🔒 Do not share
</p>

<hr style="border:0.5px solid #1e293b;margin:25px 0;">

<p style="text-align:center;color:#64748b;font-size:13px;">
If not requested, ignore this email.
</p>

<p style="text-align:center;color:#334155;font-size:12px;">
© 2026 SecurePassX
</p>

</div></div></body></html>
"""

        text_content = f"Your OTP is {otp}. Valid for 5 minutes."

        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.EMAIL_HOST_USER,
            [email],
        )

        msg.attach_alternative(html_content, "text/html")
        msg.send()

        print("✅ OTP Email sent")

    except Exception as e:
        print("❌ Email Error:", e)


# ===============================
# SEND OTP EMAIL (ASYNC)
# ===============================

def send_otp_email(email, otp):

    thread = threading.Thread(
        target=send_email_background,
        args=(email, otp)
    )

    thread.start()