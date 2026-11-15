from django.test import TestCase

# Create your tests here.



import json
from datetime import timedelta
from unittest.mock import patch

import numpy as np

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import User, FaceData, FaceSecurityState


class FaceLoginSecurityTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create(
            email="face-test@example.com",
            name="Temporary Test User"
        )

        FaceData.objects.create(
            user=self.user,
            encoding=json.dumps([0.1, 0.2, 0.3])
        )

        self.url = "/api/auth/login-face/"
        self.payload = {
            "email": self.user.email,
            "images": ["frame1", "frame2", "frame3"]
        }

    @patch("authentication.views.has_face_movement", return_value=True)
    @patch("authentication.views.get_face_encoding")
    @patch("authentication.views.decode_base64_image")
    @patch("authentication.views.compare_faces", return_value=False)
    def test_three_face_mismatches_block_login(
        self, mock_compare, mock_decode, mock_encoding, mock_liveness
    ):
        mock_decode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_encoding.return_value = np.array([0.4, 0.5, 0.6])

        for attempt in range(1, 4):
            response = self.client.post(
                self.url, self.payload, format="json"
            )

            if attempt < 3:
                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.data["failed_attempts"], attempt
                )
            else:
                self.assertEqual(response.status_code, 429)
                self.assertTrue(response.data["blocked"])

        state = FaceSecurityState.objects.get(user=self.user)

        self.assertEqual(state.failed_attempts, 3)
        self.assertIsNotNone(state.blocked_until)
        self.assertEqual(state.liveness_failed_attempts, 0)

    @patch("authentication.views.has_face_movement", return_value=False)
    @patch("authentication.views.get_face_encoding")
    @patch("authentication.views.decode_base64_image")
    @patch("authentication.views.compare_faces", return_value=True)
    def test_three_liveness_failures_require_recovery(
        self, mock_compare, mock_decode, mock_encoding, mock_liveness
    ):
        mock_decode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_encoding.return_value = np.array([0.1, 0.2, 0.3])

        for attempt in range(1, 4):
            response = self.client.post(
                self.url, self.payload, format="json"
            )

            if attempt < 3:
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.data["recovery_required"])
            else:
                self.assertEqual(response.status_code, 403)
                self.assertTrue(response.data["recovery_required"])
                self.assertFalse(response.data["allow_face_update"])

        state = FaceSecurityState.objects.get(user=self.user)

        self.assertEqual(state.liveness_failed_attempts, 3)
        self.assertEqual(state.failed_attempts, 0)
        self.assertIsNone(state.blocked_until)

    @patch("authentication.views.has_face_movement", return_value=True)
    @patch("authentication.views.get_face_encoding")
    @patch("authentication.views.decode_base64_image")
    @patch("authentication.views.compare_faces", return_value=True)
    def test_successful_face_login_resets_both_counters(
        self, mock_compare, mock_decode, mock_encoding, mock_liveness
    ):
        state = FaceSecurityState.objects.create(
            user=self.user,
            failed_attempts=2,
            liveness_failed_attempts=2,
            last_failed_at=timezone.now(),
            last_liveness_failed_at=timezone.now()
        )

        mock_decode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_encoding.return_value = np.array([0.1, 0.2, 0.3])

        response = self.client.post(
            self.url, self.payload, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        state.refresh_from_db()

        self.assertEqual(state.failed_attempts, 0)
        self.assertEqual(state.liveness_failed_attempts, 0)
        self.assertIsNone(state.blocked_until)
        self.assertIsNone(state.last_failed_at)
        self.assertIsNone(state.last_liveness_failed_at)

    @patch("authentication.views.has_face_movement", return_value=False)
    @patch("authentication.views.get_face_encoding")
    @patch("authentication.views.decode_base64_image")
    @patch("authentication.views.compare_faces", return_value=True)
    def test_liveness_failure_does_not_increment_mismatch_counter(
        self, mock_compare, mock_decode, mock_encoding, mock_liveness
    ):
        state = FaceSecurityState.objects.create(
            user=self.user,
            failed_attempts=1
        )

        mock_decode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_encoding.return_value = np.array([0.1, 0.2, 0.3])

        response = self.client.post(
            self.url, self.payload, format="json"
        )

        self.assertEqual(response.status_code, 400)

        state.refresh_from_db()

        self.assertEqual(state.failed_attempts, 0)
        self.assertEqual(state.liveness_failed_attempts, 1)
