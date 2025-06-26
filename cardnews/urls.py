# cardnews/urls.py
from django.urls import path
from . import views

app_name = 'cardnews'

urlpatterns = [
    path('', views.cardnews_home, name='home'),
    path('cluster/<int:cluster_number>/', views.cardnews_index, name='card'),
    path('toggle_like/<int:bill_id>/', views.toggle_like, name='toggle_like'), # 좋아요 기능
]
