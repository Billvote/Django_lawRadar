# main/urls.py
from django.urls import path           # Django URL 라우터[4]
from .views import home, autocomplete  # 뷰 함수 임포트[8]

app_name = "main"                      # 네임스페이스 선언[4]

urlpatterns = [
    path("", home, name="home"),                               # 홈 화면[4]
    path("api/autocomplete/", autocomplete, name="autocomplete"),  # 자동완성 API[8]
]
