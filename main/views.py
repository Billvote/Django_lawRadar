from django.shortcuts import render
from django.db.models import Q
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
    if query:
        results = Bill.objects.filter(
            Q(title__icontains=query) |
            Q(summary__icontains=query) |
            Q(cluster_keyword__icontains=query)
        )
    context = {
        'query': query,
        'results': results,
    }
    return render(request, 'search.html', context)