from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.core.cache import cache
from django.db import connection
from django.db.models import (
    Count, Max, OuterRef, Subquery, F, Value, CharField
)
from billview.models import Bill
from geovote.models import Vote
import logging

logger = logging.getLogger(__name__)




# ──────────────────────── 클러스터 상세 index (hashtag 페이지) ─────
from django.views.decorators.cache import cache_page

@cache_page(60 * 5)                       # 5분 캐시
def cluster_index(request, cluster_number):
    try:
        cluster_number = int(cluster_number)
    except ValueError:
        return render(request, 'cluster_index.html', {
            'cluster_number': cluster_number,
            'keywords': [],
            'cluster_bill_count': 0,
            'error': '유효하지 않은 클러스터 번호입니다.'
        })

    bills = Bill.objects.filter(cluster=cluster_number).only('cluster_keyword')
    keyword_set = {kw.strip()
                   for kw_str in bills.values_list('cluster_keyword', flat=True)
                   for kw in kw_str.split(',') if kw.strip()}

    return render(request, 'cluster_index.html', {
        'cluster_number'    : cluster_number,
        'keywords'          : sorted(keyword_set),
        'cluster_bill_count': bills.count()
    })
