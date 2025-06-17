# cardnews/urls.py
from django.urls import path
from . import views

app_name = 'cardnews'

urlpatterns = [
    path('', views.cardnews_home, name='home'),
    path('cluster/<int:cluster_number>/', views.cardnews_index, name='card'),
]
