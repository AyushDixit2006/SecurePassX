
from django.db import models


class User(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, default="user")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class OTP(models.Model):
    PURPOSE_CHOICES = [
        ("register", "Registration"),
        ("login", "Login"),
        ("face_recovery", "Face Recovery"),
    ]

    email = models.EmailField()
    otp = models.CharField(max_length=6)
    attempts = models.IntegerField(default=0)
    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default="register",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Never expose the actual OTP in admin or logs.
        return f"{self.email} - {self.purpose}"


class FaceData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    encoding = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email


class BlockedUser(models.Model):
    # Existing OTP blocking model; keep separate from face blocking.
    email = models.EmailField(unique=True)
    blocked_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} blocked till {self.blocked_until}"


class LoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device = models.CharField(max_length=255, null=True, blank=True)
    login_method = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} - {self.login_method} - {self.created_at}"


class FaceAuthorization(models.Model):
    PURPOSE_CHOICES = [
        ("register_face", "Face Registration"),
        ("recover_face", "Face Recovery"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="face_authorizations",
    )
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "purpose"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.purpose}"


class FaceSecurityState(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="face_security_state",
    )
    # Face mismatch tracking (unknown face)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    last_failed_at = models.DateTimeField(null=True, blank=True)

    # Liveness failure tracking (potential face recovery)
    liveness_failed_attempts = models.PositiveSmallIntegerField(default=0)
    last_liveness_failed_at = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.failed_attempts} face failures"
