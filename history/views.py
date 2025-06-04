from django.views.generic import ListView, DetailView
from billview.models import Bill
from django.db import models

class BillHistoryListView(ListView):
    model = Bill
    template_name = 'history/history_list.html'
    context_object_name = 'bills'
    paginate_by = 10

    def get_queryset(self):
        latest_ids = (
            Bill.objects.exclude(label__isnull=True)
            .values('label')
            .annotate(latest_id=models.Max('id'))
            .values_list('latest_id', flat=True)
        )
        return Bill.objects.filter(id__in=latest_ids).order_by('-created_at')

class BillHistoryDetailView(DetailView):
    model = Bill
    template_name = 'history/bill_detail.html'
    context_object_name = 'bill'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_bill = self.get_object()
        # 의안번호 내림차순(큰 번호가 위) 정렬
        related_bills = Bill.objects.filter(
            label=current_bill.label
        ).order_by('-bill_number')
        page = self.request.GET.get('page', 1)
        context['related_bills'] = related_bills
        context['list_page'] = page
        return context
