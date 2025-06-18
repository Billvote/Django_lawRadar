# search/search_service.py
"""
공통 검색·자동완성 서비스
────────────────────────────────────────────────────────
두 앱(main · history) 모두 동일한 로직을 사용하도록 묶어 둔다.
- BASE_Q            : 라벨별 '최신 1건' 필터를 적용한 기본 QuerySet
- keyword_exists()  : 단어가 실제 검색 결과를 1건이라도 만들면 True
- autocomplete()    : 입력어와 가장 '비슷한' 후보 10개 반환
    * 완전 일치        → 최상단
    * 접두사(시작) 일치 → 그다음, 더 짧은 단어가 먼저
    * 나머지           → difflib.SequenceMatcher 유사도 높은 순
"""

from difflib import SequenceMatcher
from typing import List, Set

from django.db.models import Q, OuterRef, Subquery
from billview.models import Bill

# ───────────────────────────────────────────────────────
# 1. 최신 1건만 남기는 공통 Subquery
# ───────────────────────────────────────────────────────
BASE_Q = Bill.objects.filter(
    id__in=Subquery(
        Bill.objects
            .filter(label=OuterRef("label"))
            .order_by("-bill_number")
            .values("id")[:1]
    )
)

# ───────────────────────────────────────────────────────
# 2. 검색 결과 존재 여부
# ───────────────────────────────────────────────────────
def keyword_exists(word: str) -> bool:
    return BASE_Q.filter(
        Q(title__icontains=word) |
        Q(summary__icontains=word) |
        Q(cleaned__icontains=word) |
        Q(cluster_keyword__icontains=word)
    ).exists()

# ───────────────────────────────────────────────────────
# 3. 유사도 계산 (0.0 ~ 1.0)
# ───────────────────────────────────────────────────────
def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

# ───────────────────────────────────────────────────────
# 4. 자동완성
# ───────────────────────────────────────────────────────
def autocomplete(term: str) -> List[str]:
    """
    두 글자 이상 입력 시 ‑ 실제 결과 ≥ 1건인 제목·키워드 최대 10개 반환
    정렬 기준
      0) 완전 일치
      1) 접두사 일치(짧은 단어가 먼저)
      2) 나머지  → 유사도 내림차순
    """
    term = term.strip()
    if len(term) < 2:
        return []

    term_l = term.lower()

    # ① 제목 후보 (최신 bill_number 순 5개)
    titles = list(
        BASE_Q.filter(title__icontains=term)
              .order_by("-bill_number")
              .values_list("title", flat=True)[:5]
    )

    # ② 키워드 후보
    kw_set: Set[str] = set()
    for row in (
        Bill.objects
            .filter(cluster_keyword__icontains=term)
            .order_by("-bill_number")
            .values_list("cluster_keyword", flat=True)[:200]
    ):
        for raw in (row or "").split(","):
            kw = raw.strip()
            if (
                kw and term_l in kw.lower() and
                kw not in kw_set and keyword_exists(kw)
            ):
                kw_set.add(kw)
            if len(kw_set) >= 10:
                break
        if len(kw_set) >= 10:
            break

    merged = list(dict.fromkeys(titles + list(kw_set)))  # 중복 제거(순서 유지)

    # ── 정렬 함수 정의
    def sort_key(word: str):
        w = word.lower()
        if w == term_l:                            # 0) 완전 일치
            return (0, 0)
        if w.startswith(term_l):                  # 1) 접두사 일치
            return (1, len(w))                    # 짧은 단어 먼저
        # 2) 유사도 높은 순 (유사도 값 음수로 변환 → 내림차순 효과)
        return (2, -_similar(term_l, w))

    merged.sort(key=sort_key)
    return merged[:10]
