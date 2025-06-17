"""
history/views.py
────────────────────────────────────────────────────────────────────────
• index()              : 클러스터 전체 목록(사이드 페이지)
• BillHistoryListView  : 의안 리스트 + 검색(keyword) + 클러스터 필터(cluster)
• BillHistoryDetailView: 의안 상세
• cluster_index()      : 해시태그 클릭 시 /?cluster=<id> 로 리다이렉트
"""

from django.shortcuts import render, redirect          # ← redirect 추가
from django.urls import reverse                        # ← cluster_index용
from django.views.generic import ListView, DetailView
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, OuterRef, Subquery, F
from billview.models import Bill
from geovote.models import Vote
import logging, random

logger = logging.getLogger(__name__)

# ───────────── 색상 팔레트 ─────────────
PALETTE = [
    '#bef264', '#67e8f9', '#f9a8d4', '#fde68a', '#fdba74',
    '#6ee7b7', '#c3b4fc', '#fda4af', '#5eead4', '#34d399',
    '#f472b6', '#facc15', '#fb7185', '#818cf8', '#38bdf8'
]

# ═════════════ 클러스터 목록(사이드 페이지) ═════════════
def index(request):
    """
    /history/cluster_list/ 같은 별도 메뉴가 있다면 사용하는 간단 목록 페이지
    (urls.py 에서 index 뷰를 매핑하지 않았다면 생략 가능)
    """
    clusters = cache.get('cluster_list')
    if clusters is None:
        qs = (Bill.objects
              .filter(cluster__isnull=False, cluster__gt=0)
              .values('cluster', 'cluster_keyword')
              .distinct()
              .order_by('cluster'))
        clusters = [
            {
                'cluster': r['cluster'],
                'keyword': (r['cluster_keyword'] or '').split(',')[0].strip() or '키워드 없음'
            }
            for r in qs
        ]
        cache.set('cluster_list', clusters, 60 * 60)
    return render(request, 'cluster_list.html', {'clusters': clusters})


# ═════════════ 의안 리스트 뷰 ═════════════
class BillHistoryListView(ListView):
    model               = Bill
    template_name       = 'history_list.html'
    context_object_name = 'bills'
    paginate_by         = 20

    _qs_cache   = 60 * 5
    _dict_cache = 60 * 60

    # ── cluster → "키워드,..." 문자열 dict
    def _cluster_kw_str(self):
        d = cache.get('cluster_kw_str')
        if d is None:
            d = dict(
                Bill.objects
                    .filter(cluster__isnull=False, cluster__gt=0)
                    .values_list('cluster', 'cluster_keyword')
                    .distinct()
            )
            cache.set('cluster_kw_str', d, self._dict_cache)
        return d

    # ── cluster → {keywords…} set dict
    def _cluster_kw_set(self):
        d = cache.get('cluster_kw_set')
        if d is None:
            d = {cid: {w.strip() for w in (s or '').split(',') if w.strip()}
                 for cid, s in self._cluster_kw_str().items()}
            cache.set('cluster_kw_set', d, self._dict_cache)
        return d

    # ── 상위 N개 클러스터(대표 1키워드)
    def _top_clusters(self, n=50):
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
        cache.set(key, lst, self._dict_cache)
        return lst

    # ── 선택 클러스터와 키워드 겹치는 클러스터
    def _related_clusters(self, cid: int):
        kw_sets = self._cluster_kw_set()
        sel = kw_sets.get(cid, set())
        if not sel:
            return []
        others = []
        for c, s in kw_sets.items():
            if c == cid:
                continue
            inter = len(s & sel)
            if inter:
                rep = (self._cluster_kw_str()[c] or '').split(',')[0].strip() or '키워드 없음'
                others.append((c, rep, inter))
        others.sort(key=lambda x: (-x[2], x[0]))
        return [(c, rep) for c, rep, _ in others[:50]]

    # ── cluster → color
    def _color_map(self):
        cmap = cache.get('cluster_color_map')
        if cmap:
            return cmap
        ids = (Bill.objects
               .filter(cluster__isnull=False, cluster__gt=0)
               .values_list('cluster', flat=True)
               .distinct())
        cmap = {cid: PALETTE[(cid-1) % len(PALETTE)] for cid in ids}
        cache.set('cluster_color_map', cmap, self._dict_cache)
        return cmap

    # ---------------- QuerySet ----------------
    def get_queryset(self):
        kw     = self.request.GET.get('keyword', '').strip()
        cidstr = self.request.GET.get('cluster', '').strip()

        ck = f'qs:{kw}:{cidstr}'
        if qs := cache.get(ck):
            return qs

        qs = Bill.objects.all()
        if cidstr:
            try:
                qs = qs.filter(cluster=int(cidstr))
            except ValueError:
                logger.warning('invalid cluster param %s', cidstr)
        if kw:
            # 제목·요약도 함께 검색하려면 아래 두 줄 추가
            # qs = qs.filter(
            #     Q(title__icontains=kw) | Q(summary__icontains=kw) | Q(cluster_keyword__icontains=kw)
            # )
            qs = qs.filter(cluster_keyword__icontains=kw)

        # label별 최신안
        if connection.vendor == 'postgresql':
            qs = qs.order_by('label', '-bill_number').distinct('label')
        else:
            latest = (Bill.objects
                      .filter(label=OuterRef('label'))
                      .order_by('-bill_number')
                      .values('bill_number')[:1])
            qs = qs.annotate(latest=Subquery(latest)).filter(bill_number=F('latest'))

        # label별 개수
        cnt = (Bill.objects
               .filter(label=OuterRef('label'))
               .values('label')
               .annotate(c=Count('id'))
               .values('c')[:1])
        qs = qs.annotate(related_count=Subquery(cnt)).order_by('-bill_number')

        cache.set(ck, qs, self._qs_cache)
        return qs

    # ---------------- Context -----------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        kw      = self.request.GET.get('keyword', '').strip()
        cidstr  = self.request.GET.get('cluster', '').strip()

        ctx['query']            = kw
        ctx['selected_cluster'] = cidstr
        ctx['total_results_count'] = self.object_list.count()

        # 페이지네이션 range 계산
        if page := ctx.get('page_obj'):
            s = max(page.number-5, 1)
            e = min(s+9, page.paginator.num_pages)
            ctx['page_range'] = range(s, e+1)

        kw_str_dict  = self._cluster_kw_str()
        ctx['cluster_keywords_dict'] = kw_str_dict
        ctx['cluster_color_map']     = self._color_map()
        ctx['total_cluster_count']   = len(kw_str_dict)

        # -------- 헤더 해시태그 결정 --------
        if cidstr:                                       # cluster 파라미터
            try:
                cid = int(cidstr)
                ctx['top_clusters'] = self._related_clusters(cid)
            except ValueError:
                ctx['top_clusters'] = []

        elif kw:                                         # keyword 파라미터
            # 키워드를 포함하는 클러스터 당 1개(대표 키워드)만
            matched = []
            for cid, kw_str in kw_str_dict.items():
                if kw in kw_str:
                    rep = (kw_str or '').split(',')[0].strip() or '키워드 없음'
                    matched.append((cid, rep))
            ctx['top_clusters'] = matched

        else:                                            # 메인 화면
            tc = self._top_clusters().copy()
            random.shuffle(tc)
            ctx['top_clusters'] = tc

        return ctx


# ═════════════ 의안 상세 뷰 ═════════════
class BillHistoryDetailView(DetailView):
    model               = Bill
    template_name       = 'bill_detail.html'
    context_object_name = 'bill'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        label = self.object.label

        vote_sq = (Vote.objects
                   .filter(bill=OuterRef('pk'))
                   .order_by('date')
                   .values('date')[:1])

        related = (Bill.objects
                   .filter(label=label)
                   .annotate(vote_date=Subquery(vote_sq))
                   .only('id', 'title', 'bill_number', 'label', 'summary', 'url')
                   .order_by('-bill_number')[:10])

        helper = BillHistoryListView()
        ctx.update({
            'related_bills'        : related,
            'list_page'            : self.request.GET.get('page', '1'),
            'cluster_keywords_dict': helper._cluster_kw_str(),
            'cluster_color_map'    : helper._color_map(),
        })
        return ctx


# ═════════════ 클러스터 해시태그용 리다이렉트 ═════════════
def cluster_index(request, cluster_number: int):
    """
    /history/cluster/<int:cluster_number>/
    -> /history/?cluster=<cluster_number> 로 302 리다이렉트
    """
    url = f"{reverse('history:history_list')}?cluster={cluster_number}"
    return redirect(url)
