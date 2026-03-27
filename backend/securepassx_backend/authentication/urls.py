from django.urls import path
from . import views

from .views import login_history

urlpatterns = [

    # ===============================
    # REGISTRATION FLOW
    # ===============================

    path('send-otp/', views.send_otp, name='send_otp'),

    path('verify-otp/', views.verify_otp, name='verify_otp'),

    path('face-register/', views.face_register, name='face_register'),



    # ===============================
    # LOGIN OPTIONS
    # ===============================

    path('login-otp/', views.login_with_otp, name='login_with_otp'),

    path('login-face/', views.login_with_face, name='login_with_face'),


    #===================================
    # Face Update Option 
    #===================================

    path('update-face/', views.update_face, name='update_face'),


    #===================================
    # Login History  
    #===================================

    path('login-history/',  views.login_history, name = 'login_history'),

    #===================================
    # Check Block Status
    #===================================
    path("check-block/", views.check_block),


]