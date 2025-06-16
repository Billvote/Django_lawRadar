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


# ───────────────────────────────────────── index (클러스터 목록) ──
def index(request):
    """
    “클러스터 번호/키워드 목록” 첫 화면
    1시간 캐시 (변경이 거의 없기 때문)
    """
    clusters = cache.get('cluster_list')
    if clusters is None:
        clusters_qs = (Bill.objects
                       .filter(cluster__isnull=False, cluster__gt=0)
                       .values('cluster', 'cluster_keyword')
                       .distinct()
                       .order_by('cluster'))
        clusters = [
            {
                'cluster': c['cluster'],
                'keyword': c['cluster_keyword'] or '키워드 없음'
            }
            for c in clusters_qs if isinstance(c['cluster'], int) and c['cluster'] > 0
        ]
        cache.set('cluster_list', clusters, 60 * 60)

    return render(request, 'cluster_list.html', {'clusters': clusters})


# ──────────────────────────────── BillHistoryListView (목록) ──────
class BillHistoryListView(ListView):
    """
    1. label 별 ‘최신 의안’만 추려서 출력
    2. label 별 관련 의안 수를 한 번에 annotate
    3. keyword / cluster GET 파라미터로 필터
    4. 결과·클러스터 정보를 Redis/Memcached 캐시 (5분)
    """
    model               = Bill
    template_name       = 'history_list.html'
    context_object_name = 'bills'
    paginate_by         = 20                           # 한 페이지 20건
    _qs_cache_time      = 60 * 5                      # 5 분
    _dict_cache_time    = 60 * 60                    # 1 시간

    # ────────────── 내부 헬퍼 : 클러스터→키워드 dict, Top5 ──────────
    def _cluster_dict(self):
        data = cache.get('cluster_keywords_dict')
        if data is None:
            data = dict(
                Bill.objects
                    .filter(cluster__isnull=False, cluster__gt=0)
                    .values_list('cluster', 'cluster_keyword')
                    .distinct()
            )
            cache.set('cluster_keywords_dict', data, self._dict_cache_time)
        return data

    def _top_clusters(self):
        data = cache.get('top_clusters')
        if data is None:
            tmp = (Bill.objects
                     .filter(cluster__isnull=False, cluster__gt=0)
                     .values('cluster', 'cluster_keyword')
                     .annotate(cnt=Count('id'))
                     .order_by('-cnt')[:5])
            data = [
                (
                    c['cluster'],
                    [kw.strip() for kw in (c['cluster_keyword'] or '').split(',')
                     if kw.strip()]
                )
                for c in tmp
            ]
            cache.set('top_clusters', data, self._dict_cache_time)
        return data

    # ─────────────────────────────────── 실제 QuerySet 생성 ────────
    def get_queryset(self):
        keyword = self.request.GET.get('keyword', '').strip()
        cluster = self.request.GET.get('cluster', '').strip()

        cache_key = f"bill_qs:{keyword}:{cluster}"
        if qs_cached := cache.get(cache_key):
            return qs_cached

        qs = (Bill.objects
                .only('id', 'title', 'bill_id', 'bill_number',
                      'age', 'cluster', 'cluster_keyword',
                      'label')
        )

        # 필터
        if cluster:
            try:
                qs = qs.filter(cluster=int(cluster))
            except ValueError:
                logger.warning("잘못된 cluster 파라미터: %s", cluster)
        if keyword:
            qs = qs.filter(cluster_keyword__icontains=keyword)

        # ────── label별 가장 최신 bill_number ──────
        if connection.vendor == 'postgresql':
            # DISTINCT ON 활용 (가장 빠름)
            qs = qs.order_by('label', '-bill_number').distinct('label')
        else:
            # DB 독립 서브쿼리
            latest_subq = (Bill.objects
                           .filter(label=OuterRef('label'))
                           .order_by('-bill_number')
                           .values('bill_number')[:1])
            qs = qs.annotate(latest=Subquery(latest_subq))\
                   .filter(bill_number=F('latest'))

        # ────── label별 전체 갯수 annotate (related_count) ──────
        count_subq = (Bill.objects
                      .filter(label=OuterRef('label'))
                      .values('label')
                      .annotate(c=Count('id'))
                      .values('c')[:1])
        qs = qs.annotate(related_count=Subquery(count_subq))

        qs = qs.order_by('-bill_number')
        cache.set(cache_key, qs, self._qs_cache_time)
        return qs

    # ─────────────────────────────── context 추가 ────────────────
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query']  = self.request.GET.get('keyword', '').strip()
        ctx['total_results_count'] = self.object_list.count()

        # 페이지 범위(−5 … +5)
        page_obj = ctx.get('page_obj')
        if page_obj:
            start = max(page_obj.number - 5, 1)
            end   = min(start + 9, page_obj.paginator.num_pages)
            ctx['page_range'] = range(start, end + 1)

        ctx['cluster_keywords_dict'] = self._cluster_dict()
        ctx['top_clusters']          = self._top_clusters()
        return ctx


# ─────────────────────────────── Detail 뷰 ────────────────────────
class BillHistoryDetailView(DetailView):
    model               = Bill
    template_name       = 'bill_detail.html'
    context_object_name = 'bill'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        label = self.object.label

        if not label:
            ctx['related_bills'] = []
            return ctx

        # Vote 첫 날짜 한 번에 annotate
        vote_date_sq = (Vote.objects
                          .filter(bill=OuterRef('pk'))
                          .order_by('date')
                          .values('date')[:1])

        related_qs = (Bill.objects
                        .filter(label=label)
                        .annotate(vote_date=Subquery(vote_date_sq))
                        .only('id', 'title', 'bill_number', 'label')
                        .order_by('-bill_number')[:10])

        ctx['related_bills'] = related_qs
        ctx['list_page']     = self.request.GET.get('page', '1')
        # 재활용 (캐시)
        ctx['cluster_keywords_dict'] = BillHistoryListView()._cluster_dict()
        return ctx