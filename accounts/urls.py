# Django_lawRadar/accounts/urls.py
from django.urls import path

from .views import (
    signup,
    login,
    logout,
    my_page,
    DirectPasswordResetView,
    password_reset_complete,
    ProfileUpdateView,          # ← 닉네임 수정 화면
)

app_name = "accounts"

urlpatterns = [
    # ────────────── 회원/인증 ──────────────
    path("signup/", signup, name="signup"),
    path("login/",  login,  name="login"),
    path("logout/", logout, name="logout"),

    # ────────────── 마이페이지 ──────────────
    path("mypage/", my_page, name="my_page"),

    # ────────────── 비밀번호 재설정(내부 즉시) ──────────────
    path("password-reset/",          DirectPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/complete/", password_reset_complete,          name="password_reset_complete"),

    # ────────────── 닉네임 수정 ──────────────
    path("profile/edit/", ProfileUpdateView.as_view(), name="profile_edit"),
]
