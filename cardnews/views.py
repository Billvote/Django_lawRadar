# cardnews/views.py
from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.cache import cache
from django.db.models import Count, Max
from billview.models import Bill
from geovote.models import Vote

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from accounts.models import BillLike

import random, logging, urllib.parse

logger = logging.getLogger(__name__)

# ───────────── 색상 팔레트 ─────────────
PALETTE = [
    '#bef264', '#67e8f9', '#f9a8d4', '#fde68a', '#fdba74',
    '#6ee7b7', '#c3b4fc', '#fda4af', '#5eead4', '#34d399',
    '#f472b6', '#facc15', '#fb7185', '#818cf8', '#38bdf8',
]

_DICT_CACHE = 60 * 60           # 1시간
_QS_CACHE   = 60 * 5            # 5분

# ─────────────────── helper ───────────────────
def _cluster_kw_str()  -> dict[int, str]:
    """cluster → '키워드,...' 문자열 dict"""
    d = cache.get('cluster_kw_str')
    if d is None:
        d = dict(
            Bill.objects
                .filter(cluster__gt=0)
                .values_list('cluster', 'cluster_keyword')
                .distinct()
        )
        cache.set('cluster_kw_str', d, _DICT_CACHE)
    return d

def _cluster_kw_set() -> dict[int, set[str]]:
    """cluster → {keywords…} set dict"""
    d = cache.get('cluster_kw_set')
    if d is None:
        d = {cid: {w.strip() for w in (s or '').split(',') if w.strip()}
             for cid, s in _cluster_kw_str().items()}
        cache.set('cluster_kw_set', d, _DICT_CACHE)
    return d

def _top_clusters(n=24) -> list[tuple[int, str]]:
    """상위 n개 클러스터 (id, 대표 1키워드) 목록"""
    key = f'top_clusters_{n}'
    lst = cache.get(key)
    if lst:
        return lst
    raw = (Bill.objects
           .filter(cluster__gt=0)
           .values('cluster', 'cluster_keyword')
           .annotate(cnt=Count('id'))
           .order_by('-cnt')[:n])
    lst = []
    for r in raw:
        rep = (r['cluster_keyword'] or '').split(',')[0].strip() or '키워드 없음'
        lst.append((r['cluster'], rep))
    cache.set(key, lst, _DICT_CACHE)
    return lst

def _related_clusters(cid: int) -> list[tuple[int, str]]:
    """선택 클러스터와 키워드가 겹치는 클러스터 50개"""
    kw_sets = _cluster_kw_set()
    sel = kw_sets.get(cid, set())
    if not sel:
        return []
    others = []
    cluster_kw_dict = _cluster_kw_str()
    for c, s in kw_sets.items():
        if c == cid:
            continue
        inter = len(s & sel)
        if inter:
            rep = (_cluster_kw_str()[c] or '').split(',')[0].strip() or '키워드 없음'
            others.append((c, rep, inter))
    others.sort(key=lambda x: (-x[2], x[0]))
    return [(c, rep) for c, rep, _ in others[:50]]

def _color_map():
    """cluster → 배경색"""
    cmap = cache.get('cluster_color_map')
    if cmap:
        return cmap
    ids = (Bill.objects
           .filter(cluster__gt=0)
           .values_list('cluster', flat=True)
           .distinct())
    cmap = {cid: PALETTE[(cid-1) % len(PALETTE)] for cid in ids}
    cache.set('cluster_color_map', cmap, _DICT_CACHE)
    return cmap

# ─────────────────── 메인 뷰 ───────────────────
def cardnews_home(request):
    """
    카드뉴스 메인 (/cardnews/) – 검색어, 클러스터 필터, 해시태그 헤더 포함
    """
    kw     = request.GET.get('keyword', '').strip()
    cidstr = request.GET.get('cluster', '').strip()

    # ── 의안 QuerySet (캐시 포함)
    ck = f'cardnews_qs:{kw}:{cidstr}'
    qs = cache.get(ck)
    if qs is None:
        qs = Bill.objects.all()
        if cidstr:
            try:
                qs = qs.filter(cluster=int(cidstr))
            except ValueError:
                qs = qs.none()
        if kw:
            qs = qs.filter(cluster_keyword__icontains=kw)
        qs = qs.order_by('-bill_number')
        cache.set(ck, qs, _QS_CACHE)

    # ── 공통 컨텍스트
    kw_str_dict = _cluster_kw_str()
    ctx = {
        'bills'                 : qs[:20],               # 필요한 만큼만
        'query'                 : kw,
        'selected_cluster'      : cidstr,
        'total_results_count'   : qs.count(),
        'cluster_keywords_dict' : kw_str_dict,
        'cluster_color_map'     : _color_map(),
        'total_cluster_count'   : len(kw_str_dict),
    }

    # ── 헤더 해시태그 결정 --------------------
    if cidstr:                                          # cluster 파라미터
        try:
            cid = int(cidstr)
            ctx['top_clusters'] = _related_clusters(cid)
        except ValueError:
            ctx['top_clusters'] = []

    elif kw:                                            # keyword 파라미터
        matched = [(cid,
                    (s or '').split(',')[0].strip() or '키워드 없음')
                   for cid, s in kw_str_dict.items() if kw in s]
        ctx['top_clusters'] = matched

    else:                                               # 메인 화면
        tc = _top_clusters().copy()
        random.shuffle(tc)
        ctx['top_clusters'] = tc
    # ------------------------------------------

    return render(request, 'cardnews_home.html', ctx)

# ─────────────────── 클러스터 해시태그용 리다이렉트 ───────────────────
def card_index(request, cluster_number: int):
    """
    /cardnews/cluster/<int:cluster_number>/ →
    /cardnews/?cluster=<cluster_number> 로 302 리다이렉트
    """
    url = f"{reverse('cardnews:home')}?cluster={cluster_number}"
    return redirect(url)

# 컬러 매핑
def _generate_label_color_map(labels: list[str]) -> dict[str, str]:
    color_palette = [
        '#34d399', '#f9a8d4', '#93c5fd', '#fdba74', '#c3b4fc',
        '#bef264', '#fdbaaa', '#38bdf8', '#fcd34d', '#a5b4fc',
        '#6ee7b7', '#fca5a5', '#67e8f9', '#fb7185', '#bbf7d0',
        '#fde68a', '#818cf8', '#fda4af', '#86efac', '#facc15',
        '#5eead4', '#f472b6', '#fbbf24'
    ]
    return {label: color_palette[i % len(color_palette)] for i, label in enumerate(labels)}

# 좋아요 기능
@require_POST
@login_required
def toggle_like(request, bill_id):
    try:
        bill = Bill.objects.get(id=bill_id)
    except Bill.DoesNotExist:
        return JsonResponse({'error': 'Bill not found'}, status=404)
    liked, created = BillLike.objects.get_or_create(user=request.user, bill=bill)

    if not created:
        liked.delete()
        return JsonResponse({'liked': False})
    return JsonResponse({'liked': True})

# 카드 뉴스
# @cache_page(60 * 5)                       # 5분 캐시
def cardnews_index(request, cluster_number):
    try:
        cluster_number = int(cluster_number)
    except ValueError:
        return render(request, 'cardnews.html', {
            'cluster_number': cluster_number,
            'keywords': [],
            'cluster_bill_count': 0,
            'error': '유효하지 않은 클러스터 번호입니다.'
        })
    
    bills = Bill.objects.filter(cluster=cluster_number).annotate(
        latest_vote_date=Max('vote__date')  # Vote 모델에서 Bill FK 필드명은 vote__date
    ).only('pk', 'card_news_content', 'cluster_keyword', 'label'
    ).order_by('-bill_number')
    
    keyword_set = set()
    for kw_str in bills.values_list('cluster_keyword', flat=True):
        if kw_str:
            keyword_set.update(kw.strip() for kw in kw_str.split(',') if kw.strip())

    sorted_keywords = sorted(keyword_set)

    # 추가: 뉴스 검색용 키워드 조합
    if sorted_keywords:
        # 2개 글자인 keyword 필터링
        # sorted_keywords = [kw for kw in sorted_keywords if len(kw) > 2]

        or_clause = ' OR '.join(sorted_keywords)

        # 법 AND 형식 추가
        final_query = f'법 AND ({or_clause})'

        # url 인코딩
        encoded_query = urllib.parse.quote(final_query)
        google_news_url = f"https://news.google.com/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR%3Ako"
    else:
        google_news_url = None

    # 중복 없는 bill 만들기
    seen_contents = set()
    unique_bills = []
    for bill in bills:
        if bill.card_news_content not in seen_contents:
            unique_bills.append(bill)
            seen_contents.add(bill.card_news_content)

    # 중복 없는 라벨 목록 만들기
    labels = sorted({bill.label for bill in bills if bill.label})

    label_color_map = _generate_label_color_map(labels)

    # 의안 개수
    cluster_bill_count = bills.count()

    # 좋아요 버튼
    liked_ids = []
    if request.user.is_authenticated:
        liked_ids = BillLike.objects.filter(user=request.user).values_list('bill_id', flat=True)

    context = {
        'cluster_number'    : cluster_number,
        'keywords'          : sorted_keywords,
        'cluster_bills': unique_bills,
        'label_color_map': label_color_map,
        'cluster_bill_count': bills.count(),
        'google_news_url': google_news_url,
        'liked_ids': list(liked_ids),
    }
    return render(request, 'cardnews.html', context)