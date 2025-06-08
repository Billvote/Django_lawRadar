from django.urls import path
from .views import BillHistoryListView, BillHistoryDetailView, cluster_index

app_name = 'history'

urlpatterns = [
    path('', BillHistoryListView.as_view(), name='history_list'),
    path('bill/<int:pk>/', BillHistoryDetailView.as_view(), name='bill_detail'),
    path('cluster/<int:cluster_number>/', cluster_index, name='cluster_index'),
]