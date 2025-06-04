from django.views.generic import ListView, DetailView
from billview.models import Bill

class BillHistoryListView(ListView):
    model = Bill
    template_name = 'history/history_list.html'
    context_object_name = 'bills'
    paginate_by = 10
    ordering = ['-created_at']

    def get_queryset(self):
        return Bill.objects.exclude(label__isnull=True)

class BillHistoryDetailView(DetailView):
    model = Bill
    template_name = 'history/bill_detail.html'
    context_object_name = 'bill'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_bill = self.get_object()
        related_bills = Bill.objects.filter(
            label=current_bill.label
        ).order_by('created_at')
        context['related_bills'] = related_bills
        # 목록 페이지네이션 정보 전달
        page = self.request.GET.get('page', 1)
        context['list_page'] = page
        return context
