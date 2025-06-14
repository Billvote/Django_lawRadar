from django.urls import path
from .views import BillHistoryListView, BillHistoryDetailView, cluster_index  # 명시적 상대 임포트

app_name = 'history'

# 디버깅
print(f"BillHistoryListView type: {type(BillHistoryListView)}")
print(f"BillHistoryListView module: {BillHistoryListView.__module__}")
print(f"BillHistoryListView source: {BillHistoryListView.__code__.co_filename if hasattr(BillHistoryListView, '__code__') else 'No code attribute (likely a class)'}")

urlpatterns = [
    path('', BillHistoryListView.as_view(), name='history_list'),
    path('bill/<int:pk>/', BillHistoryDetailView.as_view(), name='bill_detail'),
    path('cluster/<int:cluster_number>/', cluster_index, name='cluster_index'),
]