from django.urls import path
from .views import BillHistoryListView, BillHistoryDetailView

app_name = 'history'

urlpatterns = [
    path('', BillHistoryListView.as_view(), name='history_list'),
    path('bill/<int:pk>/', BillHistoryDetailView.as_view(), name='bill_detail'),
]
