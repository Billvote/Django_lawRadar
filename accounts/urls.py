from django.urls import path

from .views import (
    signup, login, logout, my_page,
    DirectPasswordResetView, password_reset_complete,
    UsernameUpdateView,         # ← 사용자 이름 수정
)

app_name = "accounts"

urlpatterns = [
    # ───────── 회원/인증 ─────────
    path("signup/", signup, name="signup"),
    path("login/",  login,  name="login"),
    path("logout/", logout, name="logout"),

    # ───────── 마이페이지 ─────────
    path("mypage/", my_page, name="my_page"),

    # ───────── 비밀번호 재설정 ─────────
    path("password-reset/",          DirectPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/complete/", password_reset_complete,          name="password_reset_complete"),

    # ───────── 사용자 이름 변경 ─────────
    path("profile/username/", UsernameUpdateView.as_view(), name="username_edit")
,
]
