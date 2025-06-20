"""
main/views.py  ―  lawRadar 프로젝트

홈·검색 화면 및 자동완성 API를 제공한다.
연관검색어 로직은 공통 모듈 `search/search_service.py` 를 호출해
main · history 앱이 동일한 기준을 사용하도록 통합했다.
"""
from __future__ import annotations

import logging, random, re
from collections import Counter, defaultdict

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import (
    Count,
    Max,
    OuterRef,
    Q,
    Subquery,
)
from django.db.models.functions import Random
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from billview.models import Bill
from geovote.models import Vote
from search import search_service as ss           # ★ 공통 검색 모듈
from .models import VoteSummary
import random, logging, urllib.parse


logger = logging.getLogger(__name__)

# ───────────────────────── 1. 자동완성 엔드포인트 ─────────────────────────
@require_GET
def autocomplete(request):
    """
    GET /api/autocomplete/?term=<검색어>
    - 두 글자 이상 입력 시, 실제 결과가 1건 이상 존재하는
      제목·키워드 최대 10개 반환 (search_service 공통 사용)
    """
    term = request.GET.get("term", "").strip()
    if len(term) < 2:
        return JsonResponse([], safe=False)

    cache_key = f"ac:{term.lower()}"
    if (cached := cache.get(cache_key)):
        return JsonResponse(cached, safe=False)

    suggestions = ss.autocomplete(term)           # ← 공통 로직 호출
    cache.set(cache_key, suggestions, 600)        # 10 분 캐싱
    return JsonResponse(suggestions, safe=False)

# ───────────────────────── 2. 클러스터 키워드(노드) JSON ──────────────────
def cluster_keywords_json(request):
    cached = cache.get("cluster_keywords_data")
    if cached:
        return JsonResponse(cached, safe=False)

    qs = (
        Bill.objects
            .exclude(cluster_keyword__isnull=True)
            .exclude(cluster_keyword__exact="")
            .values("cluster", "cluster_keyword")
            .annotate(
                num_bills=Count("id", distinct=True),
                latest_passed_date=Max("vote__date"),
            )
            .filter(num_bills__gt=1)
            .order_by(Random())
    )
    qs_list   = list(qs[:300])
    sampled   = random.sample(qs_list, min(len(qs_list), 100))
    result    = [
        {
            "cluster_index": row["cluster"],
            "keyword"      : row["cluster_keyword"],
            "num_bills"    : row["num_bills"],
            "latest_passed_date": (
                row["latest_passed_date"].isoformat()
                if row["latest_passed_date"] else None
            ),
            "url": f"/cardnews/cluster/{row['cluster']}/",
        }
        for row in sampled
    ]
    cache.set("cluster_keywords_data", result, 600)
    return JsonResponse(result, safe=False)

# ───────────────────────── 3. 홈(갤럭시) 뷰 ───────────────────────────────
def cluster_galaxy_view(request):
    return render(request, "home.html")

def home(request):
    clusters_raw = (
        Bill.objects
            .filter(cluster__isnull=False, cluster__gt=0)
            .values("cluster", "cluster_keyword")
            .distinct()
            .order_by("cluster")
    )
    clusters = [
        {
            "cluster": row["cluster"],
            "keyword": row["cluster_keyword"] or "키워드 없음",
        }
        for row in clusters_raw
        if isinstance(row["cluster"], int) and row["cluster"] > 0
    ]
    return render(request, "home.html", {"clusters": clusters})

def aboutUs(request):
    return render(request, "aboutUs.html")

# ───────────────────────── 4. 검색 뷰 ─────────────────────────────────────
def search(request):
    query = request.GET.get("q", "").strip()
    page_obj = page_range = None
    cluster_keywords_dict = {}
    top_clusters = []
    cluster_color_map = {}
    total_results_count = 0
    google_news_url = None

    if query:
        # 🔹 최신 의안만 필터링 (중복 제거된 결과셋)
        results = (
            Bill.objects
            .filter(
                Q(title__icontains=query) |
                Q(cleaned__icontains=query) |
                Q(summary__icontains=query) |
                Q(cluster_keyword__icontains=query),
                id__in=Subquery(
                    Bill.objects
                        .filter(label=OuterRef("label"))
                        .order_by("-bill_number")
                        .values("id")[:1]
                )
            )
            .annotate(last_vote_date=Max("vote__date"))
            .order_by("-bill_number")
        )
        total_results_count = results.count()

        # 🔹 라벨별 개정 횟수
        label_counts = {
            r["label"]: r["count"]
            for r in (
                Bill.objects
                    .filter(label__in=[b.label for b in results if b.label])
                    .values("label")
                    .annotate(count=Count("id"))
            )
        }

        # 🔹 클러스터 키워드 정리 (💥 results 기준으로 바꿈!)
        cluster_to_keywords = defaultdict(set)
        for bill in results:
            if bill.cluster_keyword and bill.cluster is not None:
                for kw in bill.cluster_keyword.split(","):
                    kw = kw.strip()
                    if kw:
                        cluster_to_keywords[bill.cluster].add(kw)
        cluster_keywords_dict = {
            cid: ", ".join(sorted(kws))
            for cid, kws in cluster_to_keywords.items()
        }

        # 🔹 클러스터별 색상
        palette = [
            "#bef264", "#67e8f9", "#f9a8d4", "#fde68a", "#fdba74",
            "#6ee7b7", "#c3b4fc", "#fda4af", "#5eead4", "#34d399",
            "#f472b6", "#facc15", "#fb7185", "#818cf8", "#38bdf8",
        ]
        random.shuffle(palette)
        cluster_ids = {bill.cluster for bill in results if bill.cluster}
        cluster_color_map = {
            cid: palette[i % len(palette)] for i, cid in enumerate(cluster_ids)
        }

        # 🔹 상위 클러스터 추출
        cluster_counter = Counter(bill.cluster for bill in results if bill.cluster)
        for i, (cid, _) in enumerate(cluster_counter.most_common(2)):
            kw_str = cluster_keywords_dict.get(cid)
            if kw_str:
                top_clusters.append({
                    "cluster_id": cid,
                    "keywords": [k.strip() for k in kw_str.split(",") if k.strip()],
                    "color": palette[i % len(palette)],
                })

        # 🔹 라벨 개정 횟수, 제목 가공
        for bill in results:
            bill.label_count = label_counts.get(bill.label, "-")
            words = bill.title.split()
            bill.title_custom = (
                " ".join(words[:4]) + "<br>" + " ".join(words[4:])
            ) if len(words) > 4 else bill.title

        # 🔹 정렬 (개정 횟수 많은 순)
        results = sorted(
            results,
            key=lambda b: label_counts.get(b.label, 0),
            reverse=True,
        )

        # 🔹 페이지네이션
        paginator = Paginator(results, 9)
        page_obj = paginator.get_page(request.GET.get("page"))
        current = page_obj.number
        total = paginator.num_pages
        start = ((current - 1) // 10) * 10 + 1
        end = min(start + 9, total)
        page_range = range(start, end + 1)

        # 🔹 구글 뉴스 키워드 생성
        if top_clusters:
            search_keywords = []
            for cluster in top_clusters:
                search_keywords.extend(cluster["keywords"][:2])
            if search_keywords:
                final_query = " OR ".join(search_keywords)
                final_query = f"법 AND ({final_query})"
                encoded_query = urllib.parse.quote(final_query)
                google_news_url = f"https://news.google.com/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR%3Ako"

    context = {
        "query": query,
        "page_obj": page_obj,
        "page_range": page_range,
        "total_results_count": total_results_count,
        "cluster_keywords_dict": cluster_keywords_dict,
        "top_clusters": top_clusters,
        "cluster_color_map": cluster_color_map,
        "google_news_url": google_news_url,
    }
    return render(request, "search.html", context)


# ───────────────────────── 5. 클러스터 링크 리다이렉트 ────────────────────
def cluster_index(request, cluster_number: int):
    url = f"{reverse('history:history_list')}?cluster={cluster_number}"
    return redirect(url)

# ───────────────────────── 6. 의원별 표결 통계 저장 ───────────────────────
def calculate_votesummary(member_name: str):
    # 1) 투표 집계
    votes = (
        Vote.objects
            .filter(member__name=member_name)
            .values("bill__cluster", "result")
            .annotate(count=Count("id"))
    )
    clusters = {v["bill__cluster"] for v in votes if v["bill__cluster"] is not None}

    # 2) cluster → 대표 키워드
    cluster_keywords = {}
    for b in (
        Bill.objects
            .filter(cluster__in=clusters)
            .exclude(cluster_keyword__isnull=True)
            .exclude(cluster_keyword__exact="")
            .values("cluster", "cluster_keyword")
    ):
        cid, kw = b["cluster"], b["cluster_keyword"]
        if cid not in cluster_keywords and not kw.isdigit():
            cluster_keywords[cid] = kw
    for cid in clusters:
        cluster_keywords.setdefault(cid, "알 수 없음")

    # 3) 클러스터별 전체 법안 수
    cluster_bill_counts = {
        cid: Bill.objects.filter(cluster=cid).count() for cid in clusters
    }

    # 4) 투표 결과 집계
    summary = {
        cid: {"찬성": 0, "반대": 0, "기권": 0, "불참": 0}
        for cid in clusters
    }
    for v in votes:
        cid    = v["bill__cluster"]
        result = v["result"] if v["result"] in summary[cid] else "기권"
        summary[cid][result] += v["count"]

    # 5) 저장
    VoteSummary.objects.filter(member_name=member_name).delete()
    for cid in clusters:
        s = summary[cid]
        VoteSummary.objects.create(
            member_name    = member_name,
            cluster        = cid,
            cluster_keyword= cluster_keywords[cid],
            bill_count     = cluster_bill_counts.get(cid, 1),
            찬성            = s["찬성"],
            반대            = s["반대"],
            기권            = s["기권"],
            불참            = s["불참"],
        )
        total_vote_count += sum(s.values())

    return total_vote_count

# ═════════════ 5. 자동완성 JSON (공통 모듈 사용) ═════════════
@require_GET
def autocomplete(request):
    """
    /history/autocomplete/?term=<검색어>
    두 글자 이상 입력 시, 실제 결과 ≥ 1 건인 제목/키워드 최대 10개
    """
    term = request.GET.get("term", "").strip()
    if len(term) < 2:
        return JsonResponse([], safe=False)

    cache_key = f"hist-ac:{term.lower()}"
    if (cached := cache.get(cache_key)):
        return JsonResponse(cached, safe=False)

    suggestions = ss.autocomplete(term)            # ★ 공통 로직 호출
    cache.set(cache_key, suggestions, 600)         # 10 분 캐시
    return JsonResponse(suggestions, safe=False)