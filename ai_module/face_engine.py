import cv2
import face_recognition
import numpy as np


# =========================================
# FACE ENCODING
# =========================================
def get_face_encoding(image):
    """
    Extract face encoding from image
    """

    try:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb)

        if len(encodings) == 0:
            return None

        return encodings[0]

    except Exception as e:
        return None


# =========================================
# FACE COMPARISON
# =========================================
def compare_faces(known_encoding, unknown_encoding):
    """
    Compare two face encodings
    """

    try:
        known_encoding = np.array(known_encoding)

        distance = face_recognition.face_distance(
            [known_encoding],
            unknown_encoding
        )[0]

        # stricter threshold → better security
        threshold = 0.5

        return distance < threshold

    except Exception:
        return False


# =========================================
# ANTI-SPOOFING CHECK
# =========================================
def is_real_face(image):
    """
    Basic anti-spoofing:
    ✔ blur detection
    ✔ single face check
    ✔ face size check
    """

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 1️⃣ Blur detection (more strict)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

        if blur_score < 80:
            return False

        # 2. Face detection (must be exactly 1 face)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb)

        if len(face_locations) != 1:
            return False

        # 3️⃣ Face size check (avoid small / far / spoof)
        top, right, bottom, left = face_locations[0]

        face_area = (bottom - top) * (right - left)
        image_area = image.shape[0] * image.shape[1]

        if face_area / image_area < 0.08:
            return False

        return True

    except Exception:
        return False


# =========================================
# LIVE FRAME VALIDATION (for frontend flow)
# =========================================
def validate_live_frames(frames):
    """
    Validate multiple frames (basic liveness feel)

    ✔ At least 2 valid frames required
    """

    valid_count = 0

    for img in frames:

        if img is None:
            continue

        if is_real_face(img):
            valid_count += 1

    return valid_count >= 2


# =========================================
# BASIC MOVEMENT-BASED LIVENESS CHECK
# =========================================
def has_face_movement(frames):
    """
    Checks normalized facial landmark movement across frames.

    This is basic movement detection, not advanced anti-spoofing.
    """

    nose_positions = []

    try:
        for image in frames:
            if image is None:
                continue

            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            locations = face_recognition.face_locations(rgb)

            if len(locations) != 1:
                continue

            landmarks = face_recognition.face_landmarks(
                rgb,
                face_locations=locations
            )

            if len(landmarks) != 1:
                continue

            points = landmarks[0]

            if not all(
                key in points
                for key in ("nose_tip", "left_eye", "right_eye")
            ):
                continue

            nose = np.mean(points["nose_tip"], axis=0)
            left_eye = np.mean(points["left_eye"], axis=0)
            right_eye = np.mean(points["right_eye"], axis=0)

            eye_distance = np.linalg.norm(left_eye - right_eye)

            if eye_distance <= 0:
                continue

            eye_midpoint = (left_eye + right_eye) / 2

            normalized_nose = (
                nose - eye_midpoint
            ) / eye_distance

            nose_positions.append(normalized_nose)

        if len(nose_positions) < 3:
            return False

        movement = sum(
            np.linalg.norm(nose_positions[i] - nose_positions[i + 1])
            for i in range(len(nose_positions) - 1)
        )

        return movement >= 0.08

    except (ValueError, TypeError, cv2.error):
        return False