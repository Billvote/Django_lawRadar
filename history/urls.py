# history/urls.py
from django.urls import path
from .views import BillDetailView

app_name = 'history'

urlpatterns = [
    path('bill/<int:pk>/', BillDetailView.as_view(), name='bill_detail'),
]
