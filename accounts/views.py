# accounts/views.py
from collections import Counter, defaultdict
import json
import logging

from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    DirectPasswordResetForm,
)

from accounts.models import BillLike
from billview.models import Bill
from geovote.models import Age, Member, Party, Vote
from main.models import ClusterKeyword, PartyClusterStats, VoteSummary
from geovote.views import get_max_clusters_for_member


logger = logging.getLogger(__name__)

PALETTE = [
    "#bef264",
    "#67e8f9",
    "#f9a8d4",
    "#fde68a",
    "#fdba74",
    "#6ee7b7",
    "#c3b4fc",
    "#fda4af",
    "#5eead4",
    "#34d399",
    "#f472b6",
    "#facc15",
    "#fb7185",
    "#818cf8",
    "#38bdf8",
]


# ──────────────────────────────────────────────
# 1. 회원가입 · 로그인 · 로그아웃
# ──────────────────────────────────────────────
def signup(request):
    """회원가입"""
    form = CustomUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:login")
    return render(request, "signup.html", {"form": form})


def login(request):
    """로그인"""
    form = CustomAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        return redirect("home")
    return render(request, "login.html", {"form": form})


def logout(request):
    """로그아웃"""
    auth_logout(request)
    return redirect("home")


# ──────────────────────────────────────────────
# 2. 이메일 입력 + 즉시 비밀번호 재설정
# ──────────────────────────────────────────────
class DirectPasswordResetView(FormView):
    """
    이메일, 새 비밀번호 2칸을 받아 즉시 비밀번호를 변경한다
    (인증 메일 없이 내부에서 직접 처리)
    """

    form_class = DirectPasswordResetForm
    template_name = "login.html"  # 템플릿 하나에서 분기 처리
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        form.save()  # 비밀번호 저장
        return super().form_valid(form)


def password_reset_complete(request):
    """
    비밀번호 변경 완료 화면
    (login.html 내부의 password_reset_complete 분기가 렌더링된다)
    """
    return render(request, "login.html")


# ──────────────────────────────────────────────
# 3. 통계·추천 관련 보조 함수
# ──────────────────────────────────────────────
def jaccard_score(set1, set2):
    """두 키워드 집합의 Jaccard 유사도"""
    return len(set1 & set2) / len(set1 | set2) if (set1 | set2) else 0


def get_user_cluster_stats(user, cluster_num=None):
    """
    사용자가 좋아요한 법안의 클러스터별 표결 통계 + 키워드
    front-chart에서 바로 사용할 JSON 형태로 반환
    """
    liked_bills = BillLike.objects.filter(user=user).select_related("bill")
    liked_clusters = {
        bill.bill.cluster for bill in liked_bills if bill.bill.cluster is not None
    }

    # 클러스터별 키워드
    keywords_raw = ClusterKeyword.objects.filter(cluster_num__in=liked_clusters)
    cluster_keywords = {}
    for ck in keywords_raw:
        try:
            kw_list = json.loads(ck.keyword_json)
            cluster_keywords[ck.cluster_num] = ", ".join(kw_list)
        except Exception:
            cluster_keywords[ck.cluster_num] = ck.keyword_json

    # 표결 통계
    stats = PartyClusterStats.objects.filter(cluster_num__in=liked_clusters).select_related(
        "party"
    )

    # 의석수 상위 8개 정당
    party_seat_counts = {
        stat.party.party: getattr(stat.party, "seat_count", 0) for stat in stats
    }
    top_parties = sorted(party_seat_counts, key=party_seat_counts.get, reverse=True)[:8]

    result_types = ["찬성", "반대", "기권", "불참"]
    cluster_data = defaultdict(
        lambda: defaultdict(lambda: {r: 0 for r in result_types})
    )

    for row in stats:
        cluster_data[row.cluster_num][row.party.party] = {
            "찬성": round(row.support_ratio),
            "반대": round(row.oppose_ratio),
            "기권": round(row.abstain_ratio),
            "불참": round(row.absent_ratio),
        }

    # 누락된 정당은 0으로 채움
    for cluster in cluster_data:
        for party in top_parties:
            cluster_data[cluster].setdefault(party, {r: 0 for r in result_types})

    cluster_vote_data_dict = {
        str(cluster_num): {
            "cluster_num": cluster_num,
            "cluster_keywords": cluster_keywords.get(cluster_num, ""),
            "party_stats": party_stats,
        }
        for cluster_num, party_stats in cluster_data.items()
    }

    return {
        "cluster_data": cluster_vote_data_dict,
        "party_names": top_parties,
        "result_types": result_types,
    }


def recommend_party_by_interest(user, age_num=None):
    """
    사용자가 좋아요한 클러스터를 기반으로
    가장 유사/반대 경향의 정당 추천
    """
    liked_clusters = (
        BillLike.objects.filter(user=user)
        .values_list("bill__cluster", flat=True)
        .distinct()
    )
    liked_clusters = [c for c in liked_clusters if c is not None]

    if not liked_clusters:
        return None, None

    stats = PartyClusterStats.objects.filter(cluster_num__in=liked_clusters)
    if age_num:
        stats = stats.filter(age__number=age_num)

    party_summary = defaultdict(
        lambda: {
            "party": None,
            "color": None,
            "support": [],
            "oppose": [],
            "abstain": [],
            "absent": [],
        }
    )

    for row in stats:
        p = row.party.party
        party_summary[p]["party"] = p
        party_summary[p]["color"] = row.party.color
        party_summary[p]["support"].append(row.support_ratio)
        party_summary[p]["oppose"].append(row.oppose_ratio)
        party_summary[p]["abstain"].append(row.abstain_ratio)
        party_summary[p]["absent"].append(row.absent_ratio)

    results = []
    for party, data in party_summary.items():
        cnt = len(data["support"])
        if not cnt:
            continue
        results.append(
            {
                "party": party,
                "color": data["color"],
                "support": sum(data["support"]) / cnt,
                "oppose": sum(data["oppose"]) / cnt,
                "abstain": sum(data["abstain"]) / cnt,
                "absent": sum(data["absent"]) / cnt,
            }
        )

    most_similar = max(results, key=lambda x: x["support"], default=None)
    most_opposite = max(results, key=lambda x: x["oppose"], default=None)
    return most_similar, most_opposite


# 의원 추천 관련 보조 함수
MIN_VOTE_COUNT = 3

def extract_cluster_ids_from_max_clusters(max_clusters):
    """max_clusters 딕트에서 cluster_id 만 추출"""
    return {
        v["cluster_id"]
        for vt, v in max_clusters.items()
        if vt in ["찬성", "반대", "기권", "불참"] and "cluster_id" in v
    }

def get_ratio(summary, vote_type):
    total = summary.찬성 + summary.반대 + summary.기권 + summary.불참
    return getattr(summary, vote_type) / total if total else 0

def get_top_members_for_user_clusters(cluster_list, vote_type='찬성', limit=1):
    """
    여러 클러스터 후보들을 모두 모아서,
    전체 후보 중 vote_type 비율이 가장 높은 의원 1명을 추천.
    """
    candidates = []

    for cluster_id in cluster_list:
        summaries = (
            VoteSummary.objects
            .filter(cluster=cluster_id)
            .select_related("member")
        )

        # 최소 표결 수 필터링
        filtered = [
            s for s in summaries
            if (s.찬성 + s.반대 + s.기권 + s.불참) >= MIN_VOTE_COUNT
        ]

        for s in filtered:
            ratio = get_ratio(s, vote_type)
            candidates.append({
                "member": s.member,
                "cluster": cluster_id,
                "ratio": ratio,
                "bill_count": s.bill_count,
            })

    if not candidates:
        return None

    # ratio 기준으로 가장 높은 1명 선택
    top = max(candidates, key=lambda c: c["ratio"])

    return {
        "id": top["member"].id,
        "name": top["member"].name,
        "party": top["member"].party.party if top["member"].party else "소속없음",
        "bill_count": top["bill_count"],
        "ratio": round(top["ratio"] * 100, 1),
        "cluster": top["cluster"],
    }


def get_recommended_members_from_clusters(cluster_ids):
    print("추천할 cluster_ids:", cluster_ids)

    supporters = get_top_members_for_user_clusters(cluster_ids, vote_type='찬성')
    print(supporters)

    opposers = get_top_members_for_user_clusters(cluster_ids, vote_type='반대')
    print(opposers)

    return {
        'supporters': supporters,
        'opposers': opposers,
    }


# ──────────────────────────────────────────────
# 4. 마이페이지
# ──────────────────────────────────────────────
@login_required
def my_page(request):
    # ───── 좋아요 법안 목록
    liked_ids = list(
        BillLike.objects.filter(user=request.user).values_list("bill_id", flat=True)
    )
    bill_list = (
        Bill.objects.filter(id__in=liked_ids)
        .annotate(latest_vote_date=Max("vote__date"))
        .prefetch_related("vote_set")
    )

    liked_clusters = {
        bill.cluster for bill in bill_list if bill.cluster is not None
    }

    # 표결 정보 유무
    has_vote_results = (
        Vote.objects.filter(bill_id__in=liked_ids)
        .exclude(result__isnull=True)
        .exclude(result="")
        .exists()
    )

    # 클러스터 선택(쿼리 파라미터)
    cluster_num = request.GET.get("cluster_num")
    try:
        cluster_num = int(cluster_num) if cluster_num else None
    except (TypeError, ValueError):
        cluster_num = None
    if cluster_num not in liked_clusters:
        cluster_num = next(iter(liked_clusters), None)

    # --- 클러스터 빈도
    cluster_ids = [bill.cluster for bill in bill_list if bill.cluster]
    cluster_counts = dict(Counter(cluster_ids))

    # --- 클러스터별 키워드(중복 제거)
    cluster_keywords = defaultdict(set)
    for bill in bill_list:
        if bill.cluster is not None and bill.cluster_keyword:
            for kw in [k.strip() for k in bill.cluster_keyword.split(",")]:
                cluster_keywords[bill.cluster].add(kw)
    cluster_keywords = {cl: ", ".join(sorted(kws)) for cl, kws in cluster_keywords.items()}

    # --- 유사 클러스터 추천
    all_cluster_keywords = ClusterKeyword.objects.all()
    full_cluster_keywords = {
        ck.cluster_num: set(
            kw.strip() for kw in ck.keyword_json.split(",") if kw.strip()
        )
        for ck in all_cluster_keywords
        if ck.keyword_json
    }
    user_keywords = {
        kw for cid in cluster_counts for kw in full_cluster_keywords.get(cid, set())
    }
    similar_clusters = sorted(
        [
            (cid, jaccard_score(user_keywords, kws))
            for cid, kws in full_cluster_keywords.items()
            if cid not in cluster_counts
        ],
        key=lambda x: x[1],
        reverse=True,
    )[:3]
    recommended_bills = (
        Bill.objects.filter(cluster__in=[cid for cid, _ in similar_clusters])
        .exclude(id__in=liked_ids)[:10]
    )

    # --- 통계 데이터
    cluster_stats_data = get_user_cluster_stats(request.user, cluster_num)

    # --- 정당 추천
    most_similar, most_opposite = recommend_party_by_interest(request.user)

    # --- 의원 추천
    member_name = request.user.username
    max_clusters = get_max_clusters_for_member(member_name)
    liked_clusters = {bill.cluster for bill in bill_list if bill.cluster is not None}
    recommended_support_members = get_top_members_for_user_clusters(liked_clusters, vote_type='찬성')
    recommended_oppose_members = get_top_members_for_user_clusters(liked_clusters, vote_type='반대')
    print("👍 추천된 찬성 의원:", recommended_support_members)
    print("👎 추천된 반대 의원:", recommended_oppose_members)

    context = {
        # 기본
        "username": request.user.username,
        # 좋아요
        "liked_bills": bill_list,
        "liked_ids": liked_ids,
        # 클러스터 현황
        "cluster_counts": cluster_counts,
        "cluster_keywords": cluster_keywords,
        "has_vote_results": has_vote_results,
        # 추천 법안
        "recommended_bills": recommended_bills,
        "top_similar_clusters": similar_clusters,
        # 차트 데이터
        "cluster_stats_data": cluster_stats_data,
        "cluster_data": cluster_stats_data["cluster_data"],
        "party_names": cluster_stats_data["party_names"],
        "result_types": cluster_stats_data["result_types"],
        # 정당 추천
        "party_comparisons": [most_similar, most_opposite],
        "most_similar_party": most_similar,
        "most_opposite_party": most_opposite,
        # 색상 팔레트
        "palette_colors": PALETTE,
        # 의원 추천
        "max_clusters": max_clusters,
        "recommended_support_member": recommended_support_members,
        "recommended_oppose_member": recommended_oppose_members,
    }

    return render(request, "my_page.html", context)
