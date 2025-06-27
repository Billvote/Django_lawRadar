from django.urls import path
from . import views

app_name = 'accounts'
common_tmpl = 'login.html'   # login·비번재설정·완료 화면을 모두 담은 단일 템플릿

urlpatterns = [
    # ─────────── 기존 라우트 ───────────
    path('signup/',  views.signup,  name='signup'),
    path('login/',   views.login,   name='login'),
    path('logout/',  views.logout,  name='logout'),
    path('myPage/',  views.my_page, name='my_page'),

    # ─────────── 비밀번호 재설정(이메일 발송 ⨯, 내부 즉시 변경) ───────────
    path(
        'password_reset/',
        views.DirectPasswordResetView.as_view(),   # 이메일 + 새 비밀번호 입력
        name='password_reset',
    ),
    path(
        'password_reset/complete/',
        views.password_reset_complete,             # 변경 완료 안내
        name='password_reset_complete',
    ),
]
