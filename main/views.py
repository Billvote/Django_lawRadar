from django.core.paginator import Paginator
from django.shortcuts import render
from django.db.models import Q, Count
from billview.models import Bill
from geovote.models import Vote
import logging

logger = logging.getLogger(__name__)

def home(request):
    # 클러스터와 키워드 조회, 유효한 숫자 클러스터만
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
        logger.warning("No valid clusters found in database")
    return render(request, 'home.html', {'clusters': clusters})

def aboutUs(request):
    return render(request, 'aboutUs.html')

def search(request):
    query = request.GET.get('q', '')
    results = []
    page_obj = None
    page_range = None # 기본값

    if query:
        results = Bill.objects.filter(
            Q(title__icontains=query) |
            Q(summary__icontains=query) |
            Q(cluster_keyword__icontains=query)
        )
        total_results_count = results.count() # result 개수

        # results에 label count 매핑
        label_counts = (
            Bill.objects
            .filter(id__in=[bill.id for bill in results])
            .exclude(label__isnull=True)
            .values('label')
            .annotate(count=Count('id'))
        )
        label_counts = {item['label']: item['count'] for item in label_counts}

        for bill in results:
            bill.label_count = label_counts.get(bill.label, '-')

        # 페이지네이션
        paginator = Paginator(results, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        current_page = page_obj.number
        total_pages = paginator.num_pages
        max_page_buttons = 10

        group = (current_page - 1) // max_page_buttons
        start_page = group * max_page_buttons + 1
        end_page = min(start_page + max_page_buttons - 1, total_pages)
        page_range = range(start_page, end_page + 1)
        
    else:
        total_results_count = 0 # 검색어 없으면 0개
        
    context = {
        'query': query,
        'page_obj': page_obj,
        'page_range': page_range,
        'total_results_count': total_results_count,
    }
    return render(request, 'search.html', context)