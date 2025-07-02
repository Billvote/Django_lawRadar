# history/views.py
# Django 5.2 ― “개정 최다” 중복-제거(라벨별 1건)·관련횟수 내림차순 + 카드뉴스 키워드 지원

from __future__ import annotations

import logging
import random
from collections import defaultdict
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
from django.db.models.functions import Coalesce, Random
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView

from billview.models import Bill
from geovote.models import Vote
from main.models import PartyClusterStats
from search import search_service as ss

from accounts.models import BillLike
from django.utils.html import format_html_join


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
        """
        {cluster_id: '키워드1, 키워드2, ...'}
        """
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
        """
        {cluster_id: '#abcdef'}
        """
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

    # ---------- 메인 쿼리 --------------------------------
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

    # ---------- 컨텍스트 --------------------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        kw = self.request.GET.get("q", "").strip()
        cid = self.request.GET.get("cluster", "").strip()

        # 기본 컨텍스트
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

        # 최근 개정
        ctx["recent_bills"] = base_qs.order_by(
            F("last_vote_date").desc(nulls_last=True), "-bill_number"
        )[:10]

        # 개정 최다
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

        # 랜덤 법안 (기존 로직 유지)
        hot_clusters = PartyClusterStats.objects.values_list(
            "cluster_num", flat=True
        )
        candidate_bills = (
            Bill.objects.filter(cluster__in=hot_clusters)
            .annotate(last_vote_date=Subquery(vote_sq))
            .order_by(Random())[:100]
        )
        cluster_groups = defaultdict(list)
        for bill in candidate_bills:
            if bill.cluster and len(cluster_groups[bill.cluster]) < 8:
                cluster_groups[bill.cluster].append(bill)

        latest_bills = []
        for bills in cluster_groups.values():
            latest = sorted(
                [b for b in bills if b.last_vote_date],
                key=lambda b: b.last_vote_date,
                reverse=True,
            )
            if latest:
                latest_bills.append(latest[0])

        for b in latest_bills:
            if b.cluster_keyword:
                keywords = [k.strip(",.") for k in b.cluster_keyword.split()]
                b.hashtag = f"#{random.choice(keywords)}" if keywords else ""
            else:
                b.hashtag = ""

        ctx["cluster_random_latest_bills"] = latest_bills[:7]

        # 카드뉴스 키워드 (top_clusters)
        cluster_kw_dict = self._cluster_kw_str()

        # 각 클러스터의 대표 키워드(첫 단어) 추출
        all_clusters = [
            (cid, (kw_str or "").split(",")[0].strip() or "키워드 없음")
            for cid, kw_str in cluster_kw_dict.items()
        ]

        # 파라미터에 따라 노출 로직 분기
        if cid:  # cluster 파라미터가 있으면 같은 키워드를 공유하는 클러스터
            try:
                cid_int = int(cid)
                base_kw = (cluster_kw_dict.get(cid_int) or "").split(",")[0].strip()
                related = [
                    (c, w) for c, w in all_clusters
                    if c != cid_int and base_kw and base_kw in cluster_kw_dict.get(c, "")
                ]
                random.shuffle(related)
                ctx["top_clusters"] = related[:24]
            except ValueError:
                ctx["top_clusters"] = []
        elif kw:  # 검색어가 있으면 해당 단어가 포함된 클러스터
            matched = [
                (c, w) for c, w in all_clusters if kw.lower() in w.lower()
            ]
            random.shuffle(matched)
            ctx["top_clusters"] = matched[:24]
        else:  # 기본 : 인기(빈도 상위) → 랜덤 섞기
            random.shuffle(all_clusters)
            ctx["top_clusters"] = all_clusters[:24]

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
        bill = self.object
        label = bill.label

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

        # 좋아요 여부 확인
        liked_ids = set()
        if self.request.user.is_authenticated:
            liked_ids = set(
                BillLike.objects.filter(user=self.request.user, bill__label=label)
                .values_list("bill_id", flat=True)
            )

        helper = BillHistoryListView()
        ctx.update(
            {
                "related_bills": related,
                "list_page": self.request.GET.get("page", "1"),
                "cluster_keywords_dict": helper._cluster_kw_str(),
                "cluster_color_map": helper._color_map(),
                "liked_ids": liked_ids,
                # "title_custom": bill.title_custom,
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
