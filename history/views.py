# history/views.py
# Django 5.2 ― “개정 최다” 중복-제거(라벨별 1건)·관련횟수 내림차순 버전
# ──────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from typing import Dict, List

from django.core.cache import cache
from django.db import connection, models
from django.db.models import (
    Count,
    DateField,
    F,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView

from billview.models import Bill
from geovote.models import Vote
from main.models import PartyClusterStats
from search import search_service as ss

logger = logging.getLogger(__name__)

# Tailwind 500 계열 10색
PALETTE: List[str] = [
    "#6EE7B7",
    "#5EEAD4",
    "#93C5FD",
    "#A5B4FC",
    "#FDE047",
    "#FDBA74",
    "#FCA5A5",
    "#F9A8D4",
    "#C7D2FE",
    "#FECACA",
]

QS_CACHE_SEC = 60 * 5
DICT_CACHE_SEC = 60 * 60

# ---------------------------------------------------------------
# 0. 클러스터 인덱스(히트맵)
# ---------------------------------------------------------------
def index(request):
    clusters = cache.get("cluster_list")
    if clusters is None:
        qs = (
            Bill.objects.filter(cluster__isnull=False, cluster__gt=0)
            .values("cluster", "cluster_keyword")
            .distinct()
            .order_by("cluster")
        )
        clusters = [
            {
                "cluster": r["cluster"],
                "keyword": (r["cluster_keyword"] or "").split(",")[0].strip()
                or "키워드 없음",
            }
            for r in qs
        ]
        cache.set("cluster_list", clusters, DICT_CACHE_SEC)
    return render(request, "cluster_list.html", {"clusters": clusters})


# ---------------------------------------------------------------
# 1. 목록 뷰
# ---------------------------------------------------------------
class BillHistoryListView(ListView):
    model = Bill
    template_name = "history_list.html"
    context_object_name = "bills"
    paginate_by = 9

    # ---------- 내부 util ---------- #
    def _cluster_kw_str(self) -> Dict[int, str]:
        d = cache.get("cluster_kw_str")
        if d is None:
            d = dict(
                Bill.objects.filter(cluster__gt=0)
                .values_list("cluster", "cluster_keyword")
                .distinct()
            )
            cache.set("cluster_kw_str", d, DICT_CACHE_SEC)
        return d

    def _color_map(self) -> Dict[int, str]:
        cmap = cache.get("cluster_color_map")
        if cmap:
            return cmap
        ids = (
            Bill.objects.filter(cluster__gt=0)
            .values_list("cluster", flat=True)
            .distinct()
        )
        cmap = {cid: PALETTE[(cid - 1) % len(PALETTE)] for cid in ids}
        cache.set("cluster_color_map", cmap, DICT_CACHE_SEC)
        return cmap

    # ---------- 메인 쿼리 ---------- #
    def get_queryset(self):
        kw = self.request.GET.get("q", "").strip()
        cid = self.request.GET.get("cluster", "").strip()

        cache_key = f"hist_qs:{kw}:{cid}"
        if cached := cache.get(cache_key):
            return cached

        qs = Bill.objects.all()
        if cid:
            try:
                qs = qs.filter(cluster=int(cid))
            except ValueError:
                logger.warning("잘못된 cluster 파라미터 %s", cid)

        if kw:
            qs = qs.filter(
                Q(title__icontains=kw)
                | Q(cluster_keyword__icontains=kw)
                | Q(summary__icontains=kw)
                | Q(cleaned__icontains=kw)
            )

        # label별 최신안건 1건만
        if connection.vendor == "postgresql":
            qs = qs.order_by("label", "-bill_number").distinct("label")
        else:
            latest_sub = (
                Bill.objects.filter(label=OuterRef("label"))
                .order_by("-bill_number")
                .values("bill_number")[:1]
            )
            qs = qs.annotate(latest_bn=Subquery(latest_sub)).filter(
                bill_number=F("latest_bn")
            )

        # 관련 개수·최근 표결일
        cnt_sub = (
            Bill.objects.filter(label=OuterRef("label"))
            .values("label")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        vote_sub = (
            Vote.objects.filter(bill=OuterRef("pk"))
            .values("bill")
            .annotate(last=Max("date"))
            .values("last")[:1]
        )
        qs = qs.annotate(
            related_count=Subquery(cnt_sub), last_vote_date=Subquery(vote_sub)
        ).order_by("-bill_number")

        cache.set(cache_key, qs, QS_CACHE_SEC)
        return qs

    # ---------- 컨텍스트 ---------- #
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        kw = self.request.GET.get("q", "").strip()
        cid = self.request.GET.get("cluster", "").strip()

        ctx.update(
            {
                "query": kw,
                "selected_cluster": cid,
                "total_results_count": self.object_list.count(),
                "cluster_keywords_dict": self._cluster_kw_str(),
                "cluster_color_map": self._color_map(),
                "total_cluster_count": len(self._cluster_kw_str()),
            }
        )

        # 페이지 범위
        if page := ctx.get("page_obj"):
            s = max(page.number - 5, 1)
            e = min(s + 9, page.paginator.num_pages)
            ctx["page_range"] = range(s, e + 1)

        # 공통 서브쿼리
        vote_sq = (
            Vote.objects.filter(bill=OuterRef("pk"))
            .values("bill")
            .annotate(last=Max("date"))
            .values("last")[:1]
        )
        cnt_sq = (
            Bill.objects.filter(label=OuterRef("label"))
            .values("label")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        base_qs = Bill.objects.annotate(
            last_vote_date=Subquery(vote_sq),
            related_count=Subquery(cnt_sq),
        )

        # 🆕 최근 개정 (최근 표결일 → 최신 의안)
        ctx["recent_bills"] = base_qs.order_by(
            F("last_vote_date").desc(nulls_last=True), "-bill_number"
        )[:10]

        # 🔁 개정 최다 ────────────────
        #  - related_count DESC
        #  - label(원 법률)별 최신 1건만
        if connection.vendor == "postgresql":
            amended_qs = (
                base_qs.order_by("label", "-bill_number")
                .distinct("label")
                .order_by("-related_count", "-bill_number")[:10]
            )
        else:
            latest_sub = (
                Bill.objects.filter(label=OuterRef("label"))
                .order_by("-bill_number")
                .values("bill_number")[:1]
            )
            amended_qs = (
                base_qs.annotate(latest_bn=Subquery(latest_sub))
                .filter(bill_number=F("latest_bn"))
                .order_by("-related_count", "-bill_number")[:8]
            )
        ctx["amended_bills"] = amended_qs

        # ❌ 반대 최다 -------------------------------------------------------
        current_age = self.request.GET.get("age")
        age_filter = {"age": current_age} if current_age else {}

        hot_clusters = PartyClusterStats.objects.filter(**age_filter).values_list(
            "cluster_num", flat=True
        )

        ctx["opposed_bills"] = (
            Bill.objects.filter(cluster__in=hot_clusters, **age_filter)
            .annotate(
                last_vote_date=Subquery(vote_sq),
                against=Count("vote", filter=Q(vote__result="반대")),
            )
            .filter(against__gt=0)
            .order_by("-last_vote_date")[:8]
        )

        return ctx


# ---------------------------------------------------------------
# 2. 상세 뷰
# ---------------------------------------------------------------
class BillHistoryDetailView(DetailView):
    model = Bill
    template_name = "bill_detail.html"
    context_object_name = "bill"

    def get_queryset(self):
        cnt_sub = (
            Bill.objects.filter(label=OuterRef("label"))
            .values("label")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        return Bill.objects.annotate(related_count=Subquery(cnt_sub))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        label = self.object.label

        vote_sq = (
            Vote.objects.filter(bill=OuterRef("pk"))
            .order_by("date")
            .values("date")[:1]
        )
        related = (
            Bill.objects.filter(label=label)
            .annotate(
                vote_date=Subquery(vote_sq),
                sort_date=Coalesce(
                    Subquery(vote_sq), Value("1970-01-01", output_field=DateField())
                ),
            )
            .only("id", "title", "bill_number", "label", "summary", "url")
            .order_by("-sort_date", "-bill_number")
        )

        helper = BillHistoryListView()
        ctx.update(
            {
                "related_bills": related,
                "list_page": self.request.GET.get("page", "1"),
                "cluster_keywords_dict": helper._cluster_kw_str(),
                "cluster_color_map": helper._color_map(),
            }
        )
        return ctx


# ---------------------------------------------------------------
# 3. 유틸
# ---------------------------------------------------------------
def cluster_index(request, cluster_number: int):
    return redirect(f"{reverse('history:history_list')}?cluster={cluster_number}")


@require_GET
def autocomplete(request):
    term = request.GET.get("term", "").strip()
    if len(term) < 2:
        return JsonResponse([], safe=False)

    cache_key = f"hist_ac:{term.lower()}"
    if cached := cache.get(cache_key):
        return JsonResponse(cached, safe=False)

    suggestions = ss.autocomplete(term)
    cache.set(cache_key, suggestions, 600)
    return JsonResponse(suggestions, safe=False)
