# history/views.py
from django.views.generic.detail import DetailView
from django.shortcuts import get_object_or_404
from billview.models import Bill

class BillDetailView(DetailView):
    model = Bill
    template_name = 'history/bill_detail.html'
    context_object_name = 'bill'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 현재 의안의 label과 같은 모든 의안들을 가져옴
        current_bill = self.get_object()
        related_bills = Bill.objects.filter(
            label=current_bill.label
        ).order_by('-created_date')
        
        context['related_bills'] = related_bills
        context['bill_history_count'] = related_bills.count()
        
        return context
