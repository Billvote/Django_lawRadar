# search/search_service.py
from django.db.models import Q, Subquery, OuterRef
from billview.models import Bill

# 최신 1건만 남기는 공통 Subquery (검색·자동완성 공용) [1]
BASE_Q = Bill.objects.filter(
    id__in=Subquery(
        Bill.objects
            .filter(label=OuterRef("label"))
            .order_by("-bill_number")
            .values("id")[:1]
    )
)

def keyword_exists(word: str) -> bool:
    """word 가 실제 결과를 1 건 이상 만들면 True [1]"""
    return BASE_Q.filter(
        Q(title__icontains=word) |
        Q(summary__icontains=word) |
        Q(cleaned__icontains=word) |
        Q(cluster_keyword__icontains=word)
    ).exists()

def autocomplete(term: str) -> list[str]:
    """
    두 글자 이상 입력 시 ‑ 실제 결과 ≥ 1 건인
    제목·키워드 최대 10 개 반환 [2]
    """
    if len(term) < 2:
        return []

    # ① 제목 후보
    titles = list(
        BASE_Q.filter(title__icontains=term)
              .values_list("title", flat=True)[:5]
    )

    # ② 키워드 후보
    kw_set: set[str] = set()
    for row in (
        Bill.objects
            .filter(cluster_keyword__icontains=term)
            .values_list("cluster_keyword", flat=True)[:200]
    ):
        for raw in (row or "").split(","):
            kw = raw.strip()
            if (
                kw and term.lower() in kw.lower() and
                kw not in kw_set and keyword_exists(kw)
            ):
                kw_set.add(kw)
            if len(kw_set) >= 10:
                break
        if len(kw_set) >= 10:
            break

    return list(dict.fromkeys(titles + list(kw_set)))[:10]
