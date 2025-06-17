"""
history/views/views_a.py
────────────────────────────────────────────────────────────────────────
index()                : 클러스터 전체 목록(옵션)
BillHistoryListView    : 의안 리스트 + 검색 + 클러스터 필터
BillHistoryDetailView  : 의안 상세
cluster_index()        : 해시태그 클릭 시 /?cluster=<id> 로 리다이렉트
autocomplete()         : jQuery-UI 자동완성 JSON 응답 (/history/autocomplete/)
"""

from __future__ import annotations

import logging
import random
from typing import Dict, List, Set

from django.core.cache import cache
from django.db import connection
from django.db.models import (
    Count, DateField, F, OuterRef, Q, Subquery, Value,
)
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView

from billview.models import Bill
from geovote.models import Vote

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
#  팔레트 (클러스터 색상용)
# ──────────────────────────────────────────────────────────
PALETTE: List[str] = [
    "#bef264", "#67e8f9", "#f9a8d4", "#fde68a", "#fdba74",
    "#6ee7b7", "#c3b4fc", "#fda4af", "#5eead4", "#34d399",
    "#f472b6", "#facc15", "#fb7185", "#818cf8", "#38bdf8",
]

QS_CACHE_SEC   = 60 * 5      # 5분
DICT_CACHE_SEC = 60 * 60     # 1시간

# ═════════════════════════════════════════════════════════
# 1. 클러스터 전체 목록 (옵션)
# ═════════════════════════════════════════════════════════
def index(request):
    clusters = cache.get("cluster_list")
    if clusters is None:
        qs = (
            Bill.objects
            .filter(cluster__isnull=False, cluster__gt=0)
            .values("cluster", "cluster_keyword")
            .distinct()
            .order_by("cluster")
        )
        clusters = [
            {
                "cluster": r["cluster"],
                "keyword": (r["cluster_keyword"] or "").split(",")[0].strip() or "키워드 없음",
            }
            for r in qs
        ]
        cache.set("cluster_list", clusters, DICT_CACHE_SEC)
    return render(request, "cluster_list.html", {"clusters": clusters})

# ═════════════════════════════════════════════════════════
# 2. BillHistoryListView
# ═════════════════════════════════════════════════════════
class BillHistoryListView(ListView):
    model               = Bill
    template_name       = "history_list.html"
    context_object_name = "bills"
    paginate_by         = 10

    # ─── 캐시용 헬퍼 ──────────────────────────────────────────
    def _cluster_kw_str(self) -> Dict[int, str]:
        d = cache.get("cluster_kw_str")
        if d is None:
            d = dict(
                Bill.objects
                    .filter(cluster__isnull=False, cluster__gt=0)
                    .values_list("cluster", "cluster_keyword")
                    .distinct()
            )
            cache.set("cluster_kw_str", d, DICT_CACHE_SEC)
        return d

    def _cluster_kw_set(self) -> Dict[int, Set[str]]:
        d = cache.get("cluster_kw_set")
        if d is None:
            d = {cid: {w.strip() for w in (s or "").split(",") if w.strip()}
                 for cid, s in self._cluster_kw_str().items()}
            cache.set("cluster_kw_set", d, DICT_CACHE_SEC)
        return d

    def _color_map(self) -> Dict[int, str]:
        cmap = cache.get("cluster_color_map")
        if cmap:
            return cmap
        ids = (
            Bill.objects
            .filter(cluster__isnull=False, cluster__gt=0)
            .values_list("cluster", flat=True)
            .distinct()
        )
        cmap = {cid: PALETTE[(cid - 1) % len(PALETTE)] for cid in ids}
        cache.set("cluster_color_map", cmap, DICT_CACHE_SEC)
        return cmap

    # ─── 인기/연관 클러스터 ───────────────────────────────────
    def _top_clusters(self, limit: int = 50) -> List[tuple[int, str]]:
        key = f"top_clusters_{limit}"
        if lst := cache.get(key):
            return lst
        qs = (
            Bill.objects
            .filter(cluster__isnull=False, cluster__gt=0)
            .values("cluster", "cluster_keyword")
            .annotate(cnt=Count("id"))
            .order_by("-cnt")[:limit]
        )
        lst: List[tuple[int, str]] = []
        for r in qs:
            rep = (r["cluster_keyword"] or "").split(",")[0].strip() or "키워드 없음"
            lst.append((r["cluster"], rep))
        cache.set(key, lst, DICT_CACHE_SEC)
        return lst

    def _related_clusters(self, cid: int) -> List[tuple[int, str]]:
        sel = self._cluster_kw_set().get(cid, set())
        if not sel:
            return []
        result: List[tuple[int, str, int]] = []
        for c, s in self._cluster_kw_set().items():
            if c == cid:
                continue
            common = len(s & sel)
            if common:
                rep = (self._cluster_kw_str()[c] or "").split(",")[0].strip() or "키워드 없음"
                result.append((c, rep, common))
        result.sort(key=lambda x: (-x[2], x[0]))
        return [(c, rep) for c, rep, _ in result[:50]]

    # ─── QuerySet 생성 ─────────────────────────────────────────
    def get_queryset(self):
        kw     = self.request.GET.get("keyword", "").strip()
        cidstr = self.request.GET.get("cluster", "").strip()
        cache_key = f"qs:{kw}:{cidstr}"
        if cached := cache.get(cache_key):
            return cached

        qs = Bill.objects.all()
        if cidstr:
            try:
                qs = qs.filter(cluster=int(cidstr))
            except ValueError:
                logger.warning("invalid cluster param %s", cidstr)
        if kw:
            qs = qs.filter(Q(title__icontains=kw) | Q(cluster_keyword__icontains=kw))

        # label별 최신안만
        if connection.vendor == "postgresql":
            qs = qs.order_by("label", "-bill_number").distinct("label")
        else:
            latest_sub = (
                Bill.objects
                .filter(label=OuterRef("label"))
                .order_by("-bill_number")
                .values("bill_number")[:1]
            )
            qs = qs.annotate(latest_bn=Subquery(latest_sub)) \
                   .filter(bill_number=F("latest_bn"))

        # label별 개정 횟수
        cnt_sub = (
            Bill.objects
            .filter(label=OuterRef("label"))
            .values("label")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        qs = qs.annotate(related_count=Subquery(cnt_sub)).order_by("-bill_number")

        cache.set(cache_key, qs, QS_CACHE_SEC)
        return qs

    # ─── 컨텍스트 ─────────────────────────────────────────────
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        kw     = self.request.GET.get("keyword", "").strip()
        cidstr = self.request.GET.get("cluster", "").strip()

        ctx["query"]               = kw
        ctx["selected_cluster"]    = cidstr
        ctx["total_results_count"] = self.object_list.count()

        if page := ctx.get("page_obj"):
            s = max(page.number - 5, 1)
            e = min(s + 9, page.paginator.num_pages)
            ctx["page_range"] = range(s, e + 1)

        ctx["cluster_keywords_dict"] = self._cluster_kw_str()
        ctx["cluster_color_map"]     = self._color_map()
        ctx["total_cluster_count"]   = len(ctx["cluster_keywords_dict"])

        if cidstr:
            try:
                ctx["top_clusters"] = self._related_clusters(int(cidstr))
            except ValueError:
                ctx["top_clusters"] = []
        elif kw:
            ctx["top_clusters"] = [
                (cid, (kwstr or "").split(",")[0].strip() or "키워드 없음")
                for cid, kwstr in ctx["cluster_keywords_dict"].items()
                if kw.lower() in kwstr.lower()
            ]
        else:
            top = self._top_clusters().copy()
            random.shuffle(top)
            ctx["top_clusters"] = top

        return ctx

# ═════════════════════════════════════════════════════════
# 3. BillHistoryDetailView (날짜 기준 타임라인 정렬)
# ═════════════════════════════════════════════════════════
class BillHistoryDetailView(DetailView):
    model               = Bill
    template_name       = "bill_detail.html"
    context_object_name = "bill"

    # 목록과 동일하게 related_count annotate
    def get_queryset(self):
        cnt_sub = (
            Bill.objects
            .filter(label=OuterRef("label"))
            .values("label")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        return Bill.objects.annotate(related_count=Subquery(cnt_sub))

    def get_context_data(self, **kwargs):
        ctx   = super().get_context_data(**kwargs)
        label = self.object.label

        # 각 의안의 가장 빠른 Vote 날짜
        vote_sq = (
            Vote.objects
            .filter(bill=OuterRef("pk"))
            .order_by("date")
            .values("date")[:1]
        )

        related = (
            Bill.objects
            .filter(label=label)
            .annotate(
                vote_date=Subquery(vote_sq),
                sort_date=Coalesce(
                    Subquery(vote_sq),                    
                    Value("1970-01-01", output_field=DateField())
                )
            )
            .only("id", "title", "bill_number", "label", "summary", "url")
            .order_by("-sort_date", "-bill_number")      # ★ 최신 날짜 → 오래된 날짜
        )

        helper = BillHistoryListView()
        ctx.update({
            "related_bills"        : related,
            "list_page"            : self.request.GET.get("page", "1"),
            "cluster_keywords_dict": helper._cluster_kw_str(),
            "cluster_color_map"    : helper._color_map(),
        })
        return ctx

# ═════════════════════════════════════════════════════════
# 4. 해시태그 → 목록 리다이렉트
# ═════════════════════════════════════════════════════════
def cluster_index(request, cluster_number: int):
    return redirect(f"{reverse('history:history_list')}?cluster={cluster_number}")

# ═════════════════════════════════════════════════════════
# 5. 자동완성 JSON
# ═════════════════════════════════════════════════════════
def autocomplete(request):
    term = request.GET.get("term", "").strip()
    if not term or len(term) < 2:
        return JsonResponse([], safe=False)

    titles = (
        Bill.objects
        .filter(title__icontains=term)
        .values_list("title", flat=True)[:5]
    )

    kw_rows = (
        Bill.objects
        .filter(cluster_keyword__icontains=term)
        .values_list("cluster_keyword", flat=True)[:50]
    )

    kw_set: Set[str] = set()
    for row in kw_rows:
        for k in (row or "").split(","):
            if term.lower() in k.lower():
                kw_set.add(k.strip())
            if len(kw_set) >= 10:
                break
        if len(kw_set) >= 10:
            break

    suggestions = list(dict.fromkeys(list(titles) + list(kw_set)))[:10]
    return JsonResponse(suggestions, safe=False)
