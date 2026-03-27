from django.contrib import admin
from django.utils import timezone
from .models import User, OTP, FaceData
from .models import BlockedUser


# ===============================
# USER ADMIN (DASHBOARD)
# ===============================

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'created_at', 'face_count')
    search_fields = ('email',)

    def face_count(self, obj):
        return FaceData.objects.filter(user=obj).count()
    face_count.short_description = "Total Faces"


# ===============================
# OTP ADMIN (SECURITY DASHBOARD)
# ===============================

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = (
        'email',
        'otp',
        'attempts',
        'created_at'
    )

    list_filter = ('created_at',)
    search_fields = ('email',)


# ===============================
# BLOCKED USER ADMIN (SECURITY DASHBOARD)
# ===============================
@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):

    list_display = (
        'email',
        'is_blocked',
        'blocked_until',
        'created_at'
    )

    list_filter = ('blocked_until', 'created_at')
    search_fields = ('email',)

    # ✅ ADD THIS LINE HERE
    actions = ['unblock_users']

    def is_blocked(self, obj):
        if obj.blocked_until and obj.blocked_until > timezone.now():
            return True
        return False
    is_blocked.boolean = True
    is_blocked.short_description = "Blocked"

    # ✅ ADD THIS FUNCTION HERE (INSIDE CLASS)
    def unblock_users(self, request, queryset):
        queryset.update(blocked_until=timezone.now())

    unblock_users.short_description = "Unblock selected users"


# ===============================
# FACE DATA ADMIN (MULTI-FACE)
# ===============================

@admin.register(FaceData)
class FaceDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email',)