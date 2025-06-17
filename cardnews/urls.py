from django.urls import path
from .views import *

app_name = 'cardnews'

# 디버깅

urlpatterns = [
    path('', cardnews_home, name='cardnews-home'),

]