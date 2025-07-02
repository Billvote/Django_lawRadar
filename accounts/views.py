# Django_lawRadar/accounts/views.py
# ────────────────────────────────────────────────────────────────
#  accounts 앱: 회원/인증, 마이페이지, 추천 로직
#  (아이디 기반 비밀번호 재설정 + 이메일→아이디 찾기 포함)
# ────────────────────────────────────────────────────────────────
import json
import logging
from collections import Counter, defaultdict

from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, UpdateView

from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    DirectPasswordResetForm,
    UpdateUsernameForm,
    FindUsernameForm,
)

from accounts.models import BillLike
from billview.models import Bill
from geovote.models import Vote
from main.models import ClusterKeyword, PartyClusterStats, VoteSummary
from geovote.views import get_max_clusters_for_member
from django.db.models import Q


logger = logging.getLogger(__name__)
User = get_user_model()

# 공통 팔레트(15색)
PALETTE = [
    "#bef264", "#67e8f9", "#f9a8d4", "#fde68a", "#fdba74",
    "#6ee7b7", "#c3b4fc", "#fda4af", "#5eead4", "#34d399",
    "#f472b6", "#facc15", "#fb7185", "#818cf8", "#38bdf8",
]

# ──────────────────────────────────────────────
# 1. 회원가입 · 로그인 · 로그아웃
# ──────────────────────────────────────────────
def signup(request):
    form = CustomUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:login")
    return render(request, "signup.html", {"form": form})


def login(request):
    form = CustomAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        return redirect("home")
    return render(request, "login.html", {"form": form})


def logout(request):
    auth_logout(request)
    return redirect("home")

# ──────────────────────────────────────────────
# 2-A. 아이디 입력 → 즉시 비밀번호 재설정
# ──────────────────────────────────────────────
class DirectPasswordResetView(FormView):
    form_class    = DirectPasswordResetForm
    template_name = "login.html"
    success_url   = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


def password_reset_complete(request):
    return render(request, "login.html")

# ──────────────────────────────────────────────
# 2-B. 이메일 → 아이디(username) 찾기
# ──────────────────────────────────────────────
def find_username(request):
    form = FindUsernameForm(request.POST or None)
    found_username = None
    if request.method == "POST" and form.is_valid():
        found_username = form.get_username()
    return render(request, "find_username.html",
                  {"form": form, "found_username": found_username})

# ──────────────────────────────────────────────
# 3. 사용자 이름(username) 수정
# ──────────────────────────────────────────────
class UsernameUpdateView(LoginRequiredMixin, UpdateView):
    model         = User
    form_class    = UpdateUsernameForm
    template_name = "edit_username.html"
    success_url   = reverse_lazy("accounts:my_page")

    def get_object(self, queryset=None):
        return self.request.user

# ──────────────────────────────────────────────
# 4. 통계·추천 보조 함수
# ──────────────────────────────────────────────
def jaccard_score(set1, set2):
    return len(set1 & set2) / len(set1 | set2) if (set1 | set2) else 0


def get_user_cluster_stats(user):
    liked_bills = BillLike.objects.filter(user=user).select_related("bill", "bill__age")

    # 유저가 좋아요한 대수 목록 (중복 제거)
    liked_ages = sorted({lb.bill.age.number for lb in liked_bills if lb.bill.age})

    # 선택된 대수에 따라 클러스터 필터링용 변수 (처음엔 None)
    selected_age = None  # 클라이언트에서 대수 선택 후 AJAX로 다시 호출하는 구조라면 여기서 받아야 함

    # 우선 대수 미선택 시 모든 대수에 포함된 클러스터 데이터 준비
    cluster_age_pairs = set()
    for lb in liked_bills:
        bill = lb.bill
        if bill.cluster and bill.age:
            cluster_age_pairs.add((bill.cluster, bill.age.number))

    # PartyClusterStats 조회용 쿼리 조건
    query = Q()
    for cluster_num, age_num in cluster_age_pairs:
        query |= Q(cluster_num=cluster_num, age__number=age_num)

    stats = PartyClusterStats.objects.filter(query).select_related("party", "age")

    cluster_keywords = {}
    cluster_to_ages = defaultdict(set)
    for ck in ClusterKeyword.objects.filter(cluster_num__in={c for c, _ in cluster_age_pairs}):
        try:
            cluster_keywords[ck.cluster_num] = ", ".join(json.loads(ck.keyword_json))
        except Exception:
            cluster_keywords[ck.cluster_num] = ck.keyword_json

    result_types = ["찬성", "반대", "기권", "불참"]

    # 대수별 클러스터별 데이터 구조
    cluster_data = defaultdict(lambda: defaultdict(lambda: {r: 0 for r in result_types}))
    cluster_party_seats = defaultdict(dict)

    for row in stats:
        key = (row.age.number, row.cluster_num)
        party_name = row.party.party
        cluster_data[key][party_name] = {
            "찬성": round(row.support_ratio),
            "반대": round(row.oppose_ratio),
            "기권": round(row.abstain_ratio),
            "불참": round(row.absent_ratio),
        }
        cluster_party_seats[key][party_name] = getattr(row.party, "seat_count", 0)
        cluster_to_ages[row.cluster_num].add(row.age.number)

    cluster_vote_data = {}
    age_cluster_map = defaultdict(dict)
    
    for key, party_dict in cluster_data.items():
        seat_count_dict = cluster_party_seats[key]
        top8 = sorted(seat_count_dict, key=seat_count_dict.get, reverse=True)[:8]
        top8 = [str(p) for p in top8]

        for party in top8:
            party_dict.setdefault(party, {r: 0 for r in result_types})

        age_num, cluster_num = key
        if not top8:
            top8 = []

        age_cluster_map[str(age_num)][str(cluster_num)] = {
            "age_num": age_num,
            "cluster_num": cluster_num,
            "cluster_keywords": cluster_keywords.get(cluster_num, ""),
            "party_stats": {p: party_dict[p] for p in top8},
            "top_parties": top8 if top8 else [],
        }
        # print(f"cluster_num={cluster_num} top_parties={top8}")
    return {
        "liked_ages": liked_ages,
        "cluster_to_ages": {k: sorted(list(v)) for k, v in cluster_to_ages.items()},
        "cluster_data": age_cluster_map,
        "result_types": result_types,
    }

# ---- 정당 추천 --------------------------------------------------
def recommend_party_by_interest(user, age_num=None):
    liked_clusters = (
        BillLike.objects.filter(user=user)
        .values_list("bill__cluster", flat=True)
        .distinct()
    )
    liked_clusters = [c for c in liked_clusters if c]
    if not liked_clusters:
        return None, None

    qs = PartyClusterStats.objects.filter(cluster_num__in=liked_clusters)
    if age_num:
        qs = qs.filter(age__number=age_num)

    summary = defaultdict(
        lambda: {"color": None, "support": [], "oppose": [], "abstain": [], "absent": []}
    )
    for s in qs:
        d = summary[s.party.party]
        d["color"] = s.party.color
        d["support"].append(s.support_ratio)
        d["oppose"].append(s.oppose_ratio)
        d["abstain"].append(s.abstain_ratio)
        d["absent"].append(s.absent_ratio)

    results = []
    for p, d in summary.items():
        cnt = len(d["support"])
        if cnt:
            results.append(
                {
                    "party": p,
                    "color": d["color"],
                    "support": sum(d["support"]) / cnt,
                    "oppose": sum(d["oppose"]) / cnt,
                    "abstain": sum(d["abstain"]) / cnt,
                    "absent": sum(d["absent"]) / cnt,
                }
            )

    most_similar  = max(results, key=lambda x: x["support"], default=None)
    most_opposite = max(results, key=lambda x: x["oppose"],  default=None)
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

def get_top_members_for_user_clusters(cluster_list, vote_type='찬성', limit=2):
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

        filtered = [
            s for s in summaries
            if (s.찬성 + s.반대 + s.기권 + s.불참) >= MIN_VOTE_COUNT
        ]

        for s in filtered:
            candidates.append({
                "member": s.member,
                "cluster": cluster_id,
                "ratio": get_ratio(s, vote_type),
                "bill_count": s.bill_count,
            })

    if not candidates:
        return None

    top = max(candidates, key=lambda c: c["ratio"])

    return {
        "id": top["member"].id,
        "name": top["member"].name,
        "party": top["member"].party,
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
# 5. 마이페이지
# ──────────────────────────────────────────────
@login_required
def my_page(request):
    liked_ids = list(
        BillLike.objects.filter(user=request.user).values_list("bill_id", flat=True)
    )
    bill_list = (
        Bill.objects.filter(id__in=liked_ids)
        .annotate(latest_vote_date=Max("vote__date"))
        .prefetch_related("vote_set")
    )

    liked_clusters = [b.cluster for b in bill_list if b.cluster]

    # 클러스터 빈도 및 키워드
    cluster_counts = dict(Counter(liked_clusters))
    cluster_keywords = defaultdict(set)
    for b in bill_list:
        if b.cluster and b.cluster_keyword:
            cluster_keywords[b.cluster].update(
                kw.strip() for kw in b.cluster_keyword.split(",")
            )
    cluster_keywords = {
        c: ", ".join(sorted(kws)) for c, kws in cluster_keywords.items()
    }

    # 유사 클러스터 추천
    full_kw = {
        ck.cluster_num: set(k.strip() for k in ck.keyword_json.split(",") if k.strip())
        for ck in ClusterKeyword.objects.all() if ck.keyword_json
    }
    user_kw = {kw for cid in cluster_counts for kw in full_kw.get(cid, set())}
    similar_clusters = sorted(
        (
            (cid, jaccard_score(user_kw, kw))
            for cid, kw in full_kw.items()
            if cid not in cluster_counts
        ),
        key=lambda x: x[1],
        reverse=True,
    )[:3]
    recommended_bills = (
        Bill.objects.filter(cluster__in=[cid for cid, _ in similar_clusters])
        .exclude(id__in=liked_ids)[:10]
        if liked_ids else []
    )

    # 차트 데이터
    cluster_stats_data = get_user_cluster_stats(request.user)

    # 정당 추천
    most_similar, most_opposite = recommend_party_by_interest(request.user)

    # --- 의원 추천
    # rec_support = get_top_members_for_user_clusters(liked_clusters, "찬성")
    # rec_oppose  = get_top_members_for_user_clusters(liked_clusters, "반대")
    # recommended_members = get_top_members_for_user_clusters(liked_clusters, limit=5)
    member_name = request.user.username
    max_clusters = get_max_clusters_for_member(member_name)
    liked_clusters = {bill.cluster for bill in bill_list if bill.cluster is not None}
    recommended_support_members = get_top_members_for_user_clusters(liked_clusters, vote_type='찬성')
    recommended_oppose_members = get_top_members_for_user_clusters(liked_clusters, vote_type='반대')
    print("👍 추천된 찬성 의원:", recommended_support_members)
    print("👎 추천된 반대 의원:", recommended_oppose_members)

    # 최대 클러스터(시각화용)
    max_clusters = get_max_clusters_for_member(request.user.username)

    # ---- 차트를 위한 정당별 색상 매핑 ----
    all_parties = set()
    for age_dict in cluster_stats_data["cluster_data"].values():
        for cluster_data in age_dict.values():  # cluster_num별 dict
            if "top_parties" in cluster_data:
                all_parties.update(cluster_data["top_parties"])

    party_colors = {
        party_name: PALETTE[i % len(PALETTE)]
        for i, party_name in enumerate(sorted(all_parties))
    }
    # print(cluster_stats_data["cluster_data"])
    return render(request, "my_page.html", {
        "username": request.user.username,

        # 좋아요
        "liked_bills": bill_list,
        "liked_ids": liked_ids,

        # 클러스터 현황
        "cluster_counts": cluster_counts,
        "cluster_keywords": cluster_keywords,

        # 추천 법안
        "recommended_bills": recommended_bills,
        "top_similar_clusters": similar_clusters,

        # 차트 데이터
        "cluster_data": cluster_stats_data["cluster_data"],
        # "party_names": cluster_stats_data["party_names"],
        "result_types": cluster_stats_data["result_types"],
        "party_colors": party_colors,

        # 정당 추천
        "most_similar_party": most_similar,
        "most_opposite_party": most_opposite,

         # 의원 추천
        # "recommended_support_member": rec_support,
        # "recommended_oppose_member":  rec_oppose,
        "max_clusters": max_clusters,
        "recommended_support_member": recommended_support_members,
        "recommended_oppose_member": recommended_oppose_members,

        # 기타
        "max_clusters": max_clusters,
        "palette_colors": PALETTE,
    })