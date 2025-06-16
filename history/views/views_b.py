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

# @cache_page(60 * 5)                       # 5분 캐시
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
    
    votes_qs = Vote.objects.only('date', 'bill_id')
    
    # bills = Bill.objects.filter(cluster=cluster_number).only(
    #     'pk', 'card_news_content', 'cluster_keyword'
    # )
    bills = Bill.objects.filter(cluster=cluster_number).annotate(
        latest_vote_date=Max('vote__date')  # Vote 모델에서 Bill FK 필드명은 vote__date
    ).only('pk', 'card_news_content', 'cluster_keyword', 'label'
    ).order_by('-bill_number')
    
    keyword_set = set()
    for kw_str in bills.values_list('cluster_keyword', flat=True):
        if kw_str:
            kws = [kw.strip() for kw in kw_str.split(',') if kw.strip()]
            keyword_set.update(kws)
    sorted_keywords = sorted(keyword_set)

    # 중복 없는 bill 만들기
    seen_contents = set()
    unique_bills = []
    for bill in bills:
        if bill.card_news_content not in seen_contents:
            unique_bills.append(bill)
            seen_contents.add(bill.card_news_content)

    color_palette = [
    '#34d399', '#f9a8d4', '#93c5fd', '#fdba74', '#c3b4fc',
    '#bef264', '#fdbaaa', '#38bdf8', '#fcd34d', '#a5b4fc',
    '#6ee7b7', '#fca5a5', '#67e8f9', '#fb7185', '#bbf7d0',
    '#fde68a', '#818cf8', '#fda4af', '#86efac', '#facc15',
    '#5eead4', '#f472b6', '#fbbf24'
    ]

    # 중복 없는 라벨 목록 만들기
    labels = set()
    for bill in bills:
        if bill.label:  # label이 None 아니면
            labels.add(bill.label)

    sorted_labels = sorted(labels)  # 정렬(optional)

    label_color_map = {}
    for i, label in enumerate(sorted_labels):
        label_color_map[label] = color_palette[i % len(color_palette)]

    # 의안 개수
    cluster_bill_count = bills.count()

    context = {
        'cluster_number'    : cluster_number,
        'keywords'          : sorted(keyword_set),
        'cluster_bills': bills,
        'label_color_map': label_color_map,
        'cluster_bill_count': cluster_bill_count,
    }
    return render(request, 'cluster_index.html', context)