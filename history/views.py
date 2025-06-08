from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from billview.models import Bill
import logging

logger = logging.getLogger(__name__)

def index(request):
    # 클러스터와 대표 키워드 조회, 유효한 숫자 클러스터만
    clusters = Bill.objects.filter(
        cluster__isnull=False,
        cluster__gt=0  # 0보다 큰 숫자만
    ).values('cluster', 'cluster_keyword').distinct().order_by('cluster')
    clusters = [
        {'cluster': c['cluster'], 'keyword': c['cluster_keyword'] or '키워드 없음'}
        for c in clusters if isinstance(c['cluster'], int) and c['cluster'] > 0
    ]
    logger.info(f"Clusters: {clusters}")
    if not clusters:
        logger.warning("No valid clusters found")
    return render(request, 'history/index.html', {'clusters': clusters})

class BillHistoryListView(ListView):
    model = Bill
    template_name = 'history/history_list.html'
    context_object_name = 'bills'
    paginate_by = 10

    def get_queryset(self):
        keyword = self.request.GET.get('keyword')
        if keyword:
            logger.info(f"Filtering bills by keyword: {keyword}")
            return Bill.objects.filter(cluster_keyword__contains=keyword)
        return Bill.objects.all()

class BillHistoryDetailView(DetailView):
    model = Bill
    template_name = 'history/bill_detail.html'
    context_object_name = 'bill'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        logger.info(f"Retrieved bill: pk={obj.pk}, bill_id={obj.bill_id}, title={obj.title}, bill_number={obj.bill_number}, summary={obj.summary}, cluster={obj.cluster}, label={obj.label}")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        label = str(self.object.label) if self.object.label is not None else ''
        if label.strip():
            related_bills = Bill.objects.filter(label=label).order_by('-bill_number')[:10]
        else:
            related_bills = []
            logger.warning(f"No valid label for bill pk={self.object.pk}, label={self.object.label}")
        context['related_bills'] = related_bills
        context['list_page'] = self.request.GET.get('page', '1')
        logger.info(f"Related bills: {[(b.pk, b.title, b.bill_number, b.label) for b in related_bills]}")
        return context

def cluster_index(request, cluster_number):
    bills = Bill.objects.filter(cluster=cluster_number)
    keywords = set()
    for bill in bills:
        if bill.cluster_keyword:
            for keyword in bill.cluster_keyword.split(','):
                keywords.add(keyword.strip())
    logger.info(f"Cluster {cluster_number} keywords: {keywords}")
    return render(request, 'history/index.html', {
        'cluster_number': cluster_number,
        'keywords': sorted(keywords)
    })