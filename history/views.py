from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from billview.models import Bill
from django.db.models import Max
import logging

logger = logging.getLogger(__name__)

def index(request):
    clusters = Bill.objects.filter(
        cluster__isnull=False,
        cluster__gt=0
    ).values('cluster', 'cluster_keyword').distinct().order_by('cluster')
    clusters = [
        {'cluster': c['cluster'], 'keyword': c['cluster_keyword'] or '키워드 없음'}
        for c in clusters if isinstance(c['cluster'], int) and c['cluster'] > 0
    ]
    logger.info(f"Clusters: {clusters}")
    if not clusters:
        logger.warning("No valid clusters found")
    return render(request, 'cluster_list.html', {'clusters': clusters})

class BillHistoryListView(ListView):
    model = Bill
    template_name = 'history_list.html'
    context_object_name = 'bills'
    paginate_by = 10

    def get_queryset(self):
        keyword = self.request.GET.get('keyword')
        cluster = self.request.GET.get('cluster')
        queryset = Bill.objects.all()
        if cluster:
            try:
                queryset = queryset.filter(cluster=int(cluster))
                logger.info(f"Filtering bills by cluster: {cluster}")
            except ValueError:
                logger.error(f"Invalid cluster: {cluster}")
        if keyword:
            logger.info(f"Filtering bills by keyword: {keyword}")
            queryset = queryset.filter(cluster_keyword__contains=keyword)
        latest_bills = queryset.values('label').annotate(
            max_bill_number=Max('bill_number')
        ).values('label', 'max_bill_number')
        bill_ids = []
        for item in latest_bills:
            if item['label'] is not None and item['max_bill_number']:
                bill = queryset.filter(
                    label=item['label'],
                    bill_number=item['max_bill_number']
                ).first()
                if bill:
                    bill_ids.append(bill.id)
        queryset = queryset.filter(id__in=bill_ids).order_by('-bill_number')
        logger.info(f"Queryset count: {queryset.count()}")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('keyword', '')
        context['total_results_count'] = self.get_queryset().count()
        # top_clusters 추가
        clusters = Bill.objects.filter(cluster__isnull=False, cluster__gt=0).values('cluster', 'cluster_keyword').distinct()[:5]
        context['top_clusters'] = [
            (c['cluster'], [kw.strip() for kw in c['cluster_keyword'].split(',') if kw.strip()] if c['cluster_keyword'] else [])
            for c in clusters
        ]
        # page_obj와 page_range 명시적 추가 (10개씩 연속 표시)
        context['page_obj'] = context.get('page_obj')
        context['page_range'] = []
        if context['page_obj']:
            paginator = context['page_obj'].paginator
            current = context['page_obj'].number
            total = paginator.num_pages
            # 현재 페이지를 중심으로 앞뒤 5개씩, 총 10개 페이지 번호 표시
            start = max(current - 5, 1)
            end = min(start + 9, total)
            # 끝에서 10개가 안 채워지면 앞에서 채움
            start = max(end - 9, 1)
            context['page_range'] = range(start, end + 1)
        # cluster_keywords_dict 추가
        cluster_keywords_dict = {}
        for c in Bill.objects.filter(cluster__isnull=False, cluster__gt=0).values('cluster', 'cluster_keyword').distinct():
            if c['cluster'] and isinstance(c['cluster'], int):
                cluster_keywords_dict[c['cluster']] = c['cluster_keyword'] or ''
        context['cluster_keywords_dict'] = cluster_keywords_dict
        logger.info(f"Cluster keywords dict: {cluster_keywords_dict}")
        logger.info(f"Top clusters: {context['top_clusters']}")
        logger.info(f"Page obj: {context['page_obj']}")
        return context

class BillHistoryDetailView(DetailView):
    model = Bill
    template_name = 'bill_detail.html'
    context_object_name = 'bill'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        logger.info(f"Retrieved bill: pk={obj.pk}, bill_id={obj.bill_id}, title={obj.title}, bill_number={obj.bill_number}, summary={obj.summary}, cluster={obj.cluster}, label={obj.label}")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        label = self.object.label
        if label is not None:
            related_bills = Bill.objects.filter(label=label).order_by('-bill_number')[:10]
        else:
            related_bills = []
            logger.warning(f"No valid label for bill pk={self.object.pk}, label={self.object.label}")
        context['related_bills'] = related_bills
        context['list_page'] = self.request.GET.get('page', '1')
        logger.info(f"Related bills: {[(b.pk, b.title, b.bill_number, b.label) for b in related_bills]}")
        return context

def cluster_index(request, cluster_number):
    try:
        cluster_number = int(cluster_number)
        bills = Bill.objects.filter(cluster=cluster_number)
        cluster_bill_count = bills.count()
        logger.info(f"Cluster {cluster_number} bills count: {cluster_bill_count}")
        keywords = set()
        for bill in bills:
            if bill.cluster_keyword:
                logger.debug(f"Bill {bill.pk} cluster_keyword: {bill.cluster_keyword}")
                for keyword in bill.cluster_keyword.split(','):
                    kw = keyword.strip()
                    if kw:
                        keywords.add(kw)
        logger.info(f"Cluster {cluster_number} keywords: {keywords}")
        return render(request, 'cluster_index.html', {
            'cluster_number': cluster_number,
            'keywords': sorted(keywords),
            'cluster_bill_count': cluster_bill_count
        })
    except ValueError:
        logger.error(f"Invalid cluster_number: {cluster_number}")
        return render(request, 'cluster_index.html', {
            'cluster_number': cluster_number,
            'keywords': [],
            'cluster_bill_count': 0,
            'error': '유효하지 않은 클러스터 번호입니다.'
        })
