# dashboard/urls.py
from django.urls import path
from . import views as dashboard_v

app_name = "dashboard"   # 네임스페이스 ─ {% url 'dashboard:dashboard' 22 %}

urlpatterns = [
    path('<int:congress_num>/', dashboard_v.dashboard, name='dashboard'),
    path('power/<int:congress_num>/', dashboard_v.power, name='power'),
    path('api/cluster_chart/',  dashboard_v.cluster_chart_api, name='cluster_chart_api'),
]
