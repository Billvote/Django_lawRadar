# accounts/views.py
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required

from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    DirectPasswordResetForm,
)
from accounts.models   import BillLike
from billview.models   import Bill
from geovote.models    import Age
from main.models       import ClusterKeyword, PartyClusterStats

from collections import Counter, defaultdict
import json


# ──────────────────────────────────────────────────────────────
# 1. 회원가입 · 로그인 · 로그아웃
# ──────────────────────────────────────────────────────────────
def signup(request):
    """
    회원가입
    """
    form = CustomUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:login")
    return render(request, "signup.html", {"form": form})


def login(request):
    """
    로그인
    """
    form = CustomAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        return redirect("home")
    return render(request, "login.html", {"form": form})


def logout(request):
    """
    로그아웃
    """
    auth_logout(request)
    return redirect("home")


# ──────────────────────────────────────────────────────────────
# 2. 이메일 없이 즉시 비밀번호 재설정
# ──────────────────────────────────────────────────────────────
class DirectPasswordResetView(FormView):
    """
    이메일 + 새 비밀번호 두 칸을 받아 즉시 비밀번호를 변경한다.
    """
    form_class    = DirectPasswordResetForm
    template_name = "login.html"                 # 단일 템플릿 사용
    success_url   = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        form.save()                              # 비밀번호 저장
        return super().form_valid(form)


def password_reset_complete(request):
    """
    비밀번호 변경 완료 화면
    (login.html 내부의 password_reset_complete 분기가 렌더링된다)
    """
    return render(request, "login.html")


# ──────────────────────────────────────────────────────────────
# 3. 클러스터 통계-보조 함수
# ──────────────────────────────────────────────────────────────
def jaccard_score(set1, set2):
    """
    두 키워드 집합의 Jaccard 유사도
    """
    return len(set1 & set2) / len(set1 | set2) if (set1 | set2) else 0


def get_user_cluster_stats(user):
    """
    사용자가 좋아요한 법안의 클러스터 통계 + 정당 투표 비율 데이터 생성
    """
    liked_bills    = BillLike.objects.filter(user=user).select_related("bill")
    liked_clusters = {
        bl.bill.cluster for bl in liked_bills if bl.bill.cluster is not None
    }
    if not liked_clusters:
        return {
            "cluster_data": [],
            "party_names": [],
            "party_colors": [],
            "result_types": [],
        }

    # 가장 최근 회기(age)가 없으면 1개만 임의 선택
    age = Age.objects.order_by("-id").first()

    # 클러스터별 키워드
    keywords_raw      = ClusterKeyword.objects.filter(cluster_num__in=liked_clusters)
    cluster_keywords  = {}
    for ck in keywords_raw:
        try:
            kw_list = json.loads(ck.keyword_json)
            cluster_keywords[ck.cluster_num] = ", ".join(kw_list)
        except Exception:
            cluster_keywords[ck.cluster_num] = ck.keyword_json

    # 정당-클러스터 통계
    stats = (
        PartyClusterStats.objects.filter(cluster_num__in=liked_clusters)
        .select_related("party")
        .order_by("party__party")
    )

    party_names  = sorted({s.party.party for s in stats})
    party_colors = [
        s.party.color for s in stats if s.party.party in party_names
    ]

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

    # 누락된 정당은 0 값으로 채움
    for cluster in cluster_data:
        for party in party_names:
            cluster_data[cluster].setdefault(
                party, {r: 0 for r in result_types}
            )

    cluster_vote_data_dict = {
        str(cluster_num): {
            "cluster_num":      cluster_num,
            "cluster_keywords": cluster_keywords.get(cluster_num, ""),
            "party_stats":      party_stats,
        }
        for cluster_num, party_stats in cluster_data.items()
    }

    return {
        "cluster_data":  cluster_vote_data_dict,
        "party_names":   party_names,
        "party_colors":  party_colors,
        "result_types":  result_types,
    }


# ──────────────────────────────────────────────────────────────
# 4. 마이페이지
# ──────────────────────────────────────────────────────────────
@login_required
def my_page(request):
    """
    사용자가 좋아요한 법안 목록 · 통계 · 추천 클러스터 등을 보여주는 마이페이지
    """
    # --- 좋아요한 법안 목록
    liked_bills = BillLike.objects.filter(user=request.user).select_related("bill")
    liked_ids   = liked_bills.values_list("bill_id", flat=True)
    bill_list   = [bl.bill for bl in liked_bills]

    # --- 관심 클러스터 빈도
    cluster_ids    = [bill.cluster for bill in bill_list if bill.cluster]
    cluster_counts = dict(Counter(cluster_ids))

    # --- 클러스터별 키워드(중복 제거)
    cluster_keywords = defaultdict(set)
    for bill in bill_list:
        if bill.cluster is not None and bill.cluster_keyword:
            for kw in [k.strip() for k in bill.cluster_keyword.split(",")]:
                cluster_keywords[bill.cluster].add(kw)

    # 집합을 문자열로
    for cl, kws in cluster_keywords.items():
        cluster_keywords[cl] = ", ".join(sorted(kws))

    # --- 유사 클러스터 추천
    all_cluster_keywords = ClusterKeyword.objects.all()
    full_cluster_keywords = {
        ck.cluster_num: set(
            kw.strip() for kw in ck.keyword_json.split(",") if kw.strip()
        )
        for ck in all_cluster_keywords
        if ck.keyword_json
    }

    user_clusters = set(cluster_counts.keys())
    user_keywords = {
        kw for cid in user_clusters for kw in full_cluster_keywords.get(cid, set())
    }

    similar_clusters = [
        (cid, jaccard_score(user_keywords, kws))
        for cid, kws in full_cluster_keywords.items()
        if cid not in user_clusters
    ]
    similar_clusters.sort(key=lambda x: x[1], reverse=True)
    top_similar_clusters = similar_clusters[:3]

    recommended_bills = (
        Bill.objects.filter(cluster__in=[cid for cid, _ in top_similar_clusters])
        .exclude(id__in=liked_ids)
        .order_by("-id")[:10]
    )

    # --- 통계 데이터
    cluster_stats_data = get_user_cluster_stats(request.user)

    # --- 회기(age) 드롭다운
    ages = Age.objects.all().order_by("id")

    context = {
        # 기본 정보
        "username":  request.user.username,
        # 좋아요 목록
        "liked_bills": bill_list,
        "liked_ids":   list(liked_ids),
        # 클러스터
        "cluster_counts":   cluster_counts,
        "cluster_keywords": cluster_keywords,
        # 추천
        "recommended_bills":   recommended_bills,
        "top_similar_clusters": top_similar_clusters,
        # 통계(그래프)
        "cluster_stats_data": cluster_stats_data,
        "cluster_data":       cluster_stats_data["cluster_data"],
        "party_names":        cluster_stats_data["party_names"],
        "party_colors":       cluster_stats_data["party_colors"],
        "result_types":       cluster_stats_data["result_types"],
        # 회기 선택
        "ages": ages,
    }
    return render(request, "my_page.html", context)
