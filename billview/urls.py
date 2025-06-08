from django.urls import path
from . import views

app_name = 'billview'

urlpatterns = [
    # 클러스터 기능
    path('', views.cluster_home, name='cluster_home'),
    path('clusters/<int:cluster_num>/', views.cluster_index, name='cluster_index'),
    path('history/<str:keyword>/', views.cluster_history, name='cluster_history'),
    
    # 기존 법안 기능
    path('bills/', views.index_bill, name='index_bill'),
    path('bills/<int:id>/', views.detail_bill, name='detail_bill'),
]
