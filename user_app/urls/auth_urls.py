# app/urls/auth_urls.py

from django.urls import path
from user_app.views.auth_views import (
    RegisterAPIView, LoginAPIView, LogoutAPIView,
    PasswordResetRequestView, PasswordResetConfirmView,
    CustomTokenRefreshView
)
from rest_framework_simplejwt.views import TokenObtainPairView

app_name = 'auth'

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('logout/', LogoutAPIView.as_view(), name='logout'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/<str:token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
