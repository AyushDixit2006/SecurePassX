from django.db import models


class User(models.Model):

    name = models.CharField(max_length=100, blank=True, null=True)

    email = models.EmailField(unique=True)

    role = models.CharField(max_length=20, default="user")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class OTP(models.Model):

    email = models.EmailField()

    otp = models.CharField(max_length=6)

    # NEW FIELDS
    attempts = models.IntegerField(default=0)


    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} - {self.otp}"


class FaceData(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    encoding = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email
    


class BlockedUser(models.Model):

    email = models.EmailField(unique=True)

    blocked_until = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} blocked till {self.blocked_until}"
    

# ===============================
# LOGIN ACTIVITY (NEW)
# ===============================
class LoginActivity(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    email = models.EmailField()

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    device = models.CharField(max_length=255, null=True, blank=True)

    login_method = models.CharField(max_length=20)  # OTP / FACE

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} - {self.login_method} - {self.created_at}"