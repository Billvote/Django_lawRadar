# history/views.py  ── three extra columns: 최근‧개정최다‧랜덤  (based on paste.txt[1])
from __future__ import annotations

import logging, random
from typing import Dict, List, Set

from django.core.cache import cache
from django.db import connection
from django.db.models import (
    Count, DateField, F, Max, OuterRef, Q, Subquery, Value,
)
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView

from billview.models import Bill
from geovote.models import Vote
from search import search_service as ss

logger = logging.getLogger(__name__)

# ───────────────────────── 색상 팔레트 ─────────────────────────
PALETTE: List[str] = [
    "#bef264", "#67e8f9", "#f9a8d4", "#fde68a", "#fdba74",
    "#6ee7b7", "#c3b4fc", "#fda4af", "#5eead4", "#34d399",
    "#f472b6", "#facc15", "#fb7185", "#818cf8", "#38bdf8",
]
QS_CACHE_SEC   = 60 * 5
DICT_CACHE_SEC = 60 * 60

# ═════════════ 1. 클러스터 전체 목록 ═════════════
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
                "keyword": (r["cluster_keyword"] or "").split(",")[0].strip()
                           or "키워드 없음",
            } for r in qs
        ]
        cache.set("cluster_list", clusters, DICT_CACHE_SEC)
    return render(request, "cluster_list.html", {"clusters": clusters})

# ═════════════ 2. 의안 리스트 뷰 ═════════════
class BillHistoryListView(ListView):
    model               = Bill
    template_name       = "history_list.html"
    context_object_name = "bills"
    paginate_by         = 9

    # ── 클러스터 유틸
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

    def _cluster_kw_set(self):
        d = cache.get("cluster_kw_set")
        if d is None:
            d = {
                cid: {w.strip() for w in (s or "").split(",") if w.strip()}
                for cid, s in self._cluster_kw_str().items()
            }
            cache.set("cluster_kw_set", d, DICT_CACHE_SEC)
        return d

    def _color_map(self):
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

    def _cluster_bill_count(self):
        key = "cluster_bill_count_v2"
        d = cache.get(key)
        if d is None:
            d = dict(
                Bill.objects
                    .filter(cluster__isnull=False, cluster__gt=0)
                    .values("cluster")
                    .annotate(total=Count("id"))
                    .values_list("cluster", "total")
            )
            cache.set(key, d, DICT_CACHE_SEC)
        return d

    def _top_clusters(self, limit=50):
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
        lst = [
            (
                r["cluster"],
                (r["cluster_keyword"] or "").split(",")[0].strip() or "키워드 없음",
            ) for r in qs
        ]
        cache.set(key, lst, DICT_CACHE_SEC)
        return lst

    # ── 실제 QuerySet
    def get_queryset(self):
        kw     = self.request.GET.get("keyword", "").strip()
        cidstr = self.request.GET.get("cluster", "").strip()

        cache_key = f"qs2:{kw}:{cidstr}"
        if cached := cache.get(cache_key):
            return cached

        qs = Bill.objects.all()

        if cidstr:
            try:
                qs = qs.filter(cluster=int(cidstr))
            except ValueError:
                logger.warning("잘못된 cluster 파라미터 %s", cidstr)

        if kw:
            qs = qs.filter(
                Q(title__icontains=kw) |
                Q(cluster_keyword__icontains=kw) |
                Q(summary__icontains=kw) |
                Q(cleaned__icontains=kw)
            )

        # 최신 의안만 남기기
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

        # label 별 개정 횟수
        cnt_sub = (
            Bill.objects
                .filter(label=OuterRef("label"))
                .values("label")
                .annotate(total=Count("id"))
                .values("total")[:1]
        )
        qs = qs.annotate(related_count=Subquery(cnt_sub))

        # 마지막 표결일
        vote_sub = (
            Vote.objects
                .filter(bill=OuterRef("pk"))
                .values("bill")
                .annotate(last=Max("date"))
                .values("last")[:1]
        )
        qs = qs.annotate(last_vote_date=Subquery(vote_sub))

        qs = qs.order_by("-bill_number")
        cache.set(cache_key, qs, QS_CACHE_SEC)
        return qs

    # ── 템플릿 컨텍스트
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        kw     = self.request.GET.get("keyword", "").strip()
        cidstr = self.request.GET.get("cluster", "").strip()

        ctx.update(
            {
                "query"                : kw,
                "selected_cluster"     : cidstr,
                "total_results_count"  : self.object_list.count(),
                "cluster_keywords_dict": self._cluster_kw_str(),
                "cluster_color_map"    : self._color_map(),
                "total_cluster_count"  : len(self._cluster_kw_str()),
            }
        )

        if page := ctx.get("page_obj"):
            s = max(page.number - 5, 1)
            e = min(s + 9, page.paginator.num_pages)
            ctx["page_range"] = range(s, e + 1)

        # ── 해시태그 영역
        if cidstr:
            try:
                ctx["top_clusters"] = self._related_clusters(int(cidstr))
            except ValueError:
                ctx["top_clusters"] = []
        elif kw:
            counts  = self._cluster_bill_count()
            matched = []
            for cid, kwstr in ctx["cluster_keywords_dict"].items():
                if not isinstance(cid, int):
                    continue
                rep = (kwstr or "").split(",")[0].strip() or "키워드 없음"
                if rep == kw:
                    continue
                if kw.lower() in kwstr.lower() and counts.get(cid, 0) > 0:
                    matched.append((cid, rep))
            ctx["top_clusters"] = matched
        else:
            top = self._top_clusters().copy()
            random.shuffle(top)
            ctx["top_clusters"] = top

        # ────────────────────────────────────────────────────────────
        #  추가: 최근 개정 / 개정 최다 / 랜덤  세로열용 QuerySet
        # ────────────────────────────────────────────────────────────
        # 공통 서브쿼리
        vote_sq = (
            Vote.objects
                .filter(bill=OuterRef("pk"))
                .values("bill")
                .annotate(last=Max("date"))
                .values("last")[:1]
        )
        cnt_sq = (
            Bill.objects
                .filter(label=OuterRef("label"))
                .values("label")
                .annotate(total=Count("id"))
                .values("total")[:1]
        )

        base_qs = (
            Bill.objects
                .annotate(last_vote_date=Subquery(vote_sq))
                .annotate(related_count=Subquery(cnt_sq))
        )

        ctx["recent_bills"] = (
            base_qs.order_by(
                F("last_vote_date").desc(nulls_last=True),
                "-bill_number"
            )[:10]
        )
        ctx["amended_bills"] = (
            base_qs.order_by("-related_count", "-bill_number")[:10]
        )
        ctx["random_bills"]  = base_qs.order_by("?")[:10]
        # ────────────────────────────────────────────────────────────
        return ctx

# ═════════════ 3. 의안 상세 ═════════════
class BillHistoryDetailView(DetailView):
    model               = Bill
    template_name       = "bill_detail.html"
    context_object_name = "bill"

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
                        Value("1970-01-01", output_field=DateField()),
                    ),
                )
                .only("id", "title", "bill_number", "label",
                      "summary", "url")
                .order_by("-sort_date", "-bill_number")
        )

        helper = BillHistoryListView()
        ctx.update(
            {
                "related_bills"        : related,
                "list_page"            : self.request.GET.get("page", "1"),
                "cluster_keywords_dict": helper._cluster_kw_str(),
                "cluster_color_map"    : helper._color_map(),
            }
        )
        return ctx

# ═════════════ 4. 해시태그 리다이렉트 ═════════════
def cluster_index(request, cluster_number: int):
    return redirect(f"{reverse('history:history_list')}?cluster={cluster_number}")

# ═════════════ 5. 자동완성 ═════════════
@require_GET
def autocomplete(request):
    term = request.GET.get("term", "").strip()
    if len(term) < 2:
        return JsonResponse([], safe=False)

    cache_key = f"hist-ac:{term.lower()}"
    if (cached := cache.get(cache_key)):
        return JsonResponse(cached, safe=False)

    suggestions = ss.autocomplete(term)
    cache.set(cache_key, suggestions, 600)
    return JsonResponse(suggestions, safe=False)
