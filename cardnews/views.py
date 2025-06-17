# cardnews/views.py
from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.cache import cache
from django.db.models import Count
from billview.models import Bill
import random

# ───────────── 색상 팔레트 ─────────────
PALETTE = [
    '#bef264', '#67e8f9', '#f9a8d4', '#fde68a', '#fdba74',
    '#6ee7b7', '#c3b4fc', '#fda4af', '#5eead4', '#34d399',
    '#f472b6', '#facc15', '#fb7185', '#818cf8', '#38bdf8',
]

_DICT_CACHE = 60 * 60           # 1 시간
_QS_CACHE   = 60 * 5            # 5 분

# ─────────────────── helper ───────────────────
def _cluster_kw_str():
    """cluster → '키워드,...' 문자열 dict"""
    d = cache.get('cluster_kw_str')
    if d is None:
        d = dict(
            Bill.objects
                .filter(cluster__isnull=False, cluster__gt=0)
                .values_list('cluster', 'cluster_keyword')
                .distinct()
        )
        cache.set('cluster_kw_str', d, _DICT_CACHE)
    return d

def _cluster_kw_set():
    """cluster → {keywords…} set dict"""
    d = cache.get('cluster_kw_set')
    if d is None:
        d = {cid: {w.strip() for w in (s or '').split(',') if w.strip()}
             for cid, s in _cluster_kw_str().items()}
        cache.set('cluster_kw_set', d, _DICT_CACHE)
    return d

def _top_clusters(n=50):
    """상위 n개 클러스터 (id, 대표 1키워드) 목록"""
    key = f'top_clusters_{n}'
    if lst := cache.get(key):
        return lst
    raw = (Bill.objects
           .filter(cluster__isnull=False, cluster__gt=0)
           .values('cluster', 'cluster_keyword')
           .annotate(cnt=Count('id'))
           .order_by('-cnt')[:n])
    lst = []
    for r in raw:
        rep = (r['cluster_keyword'] or '').split(',')[0].strip() or '키워드 없음'
        lst.append((r['cluster'], rep))
    cache.set(key, lst, _DICT_CACHE)
    return lst

def _related_clusters(cid: int):
    """선택 클러스터와 키워드가 겹치는 클러스터 50개"""
    kw_sets = _cluster_kw_set()
    sel = kw_sets.get(cid, set())
    if not sel:
        return []
    others = []
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
           .filter(cluster__isnull=False, cluster__gt=0)
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
def cluster_index(request, cluster_number: int):
    """
    /cardnews/cluster/<int:cluster_number>/ →
    /cardnews/?cluster=<cluster_number> 로 302 리다이렉트
    """
    url = f"{reverse('cardnews:home')}?cluster={cluster_number}"
    return redirect(url)
