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

logger = logging.getLogger(__name__)
User = get_user_model()

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
    template_name = "login.html"          # 단일 템플릿 내부 분기 사용
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
    return render(
        request,
        "find_username.html",
        {"form": form, "found_username": found_username},
    )


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
    """
    사용자가 좋아요한 클러스터별 키워드 및 정당 투표 통계 반환
    """
    liked_clusters = (
        BillLike.objects.filter(user=user)
        .values_list("bill__cluster", flat=True)
        .distinct()
    )
    liked_clusters = [c for c in liked_clusters if c]

    # 키워드
    cluster_keywords = {}
    for ck in ClusterKeyword.objects.filter(cluster_num__in=liked_clusters):
        try:
            cluster_keywords[ck.cluster_num] = ", ".join(json.loads(ck.keyword_json))
        except Exception:
            cluster_keywords[ck.cluster_num] = ck.keyword_json

    # 표결 통계
    stats = (
        PartyClusterStats.objects.filter(cluster_num__in=liked_clusters)
        .select_related("party")
    )

    result_types = ["찬성", "반대", "기권", "불참"]
    cluster_data = defaultdict(lambda: defaultdict(lambda: {r: 0 for r in result_types}))
    party_seat_counts = {}

    for row in stats:
        party_name = row.party.party
        party_seat_counts[party_name] = getattr(row.party, "seat_count", 0)
        cluster_data[row.cluster_num][party_name] = {
            "찬성": round(row.support_ratio),
            "반대": round(row.oppose_ratio),
            "기권": round(row.abstain_ratio),
            "불참": round(row.absent_ratio),
        }

    # 의석수 순 상위 8개 정당
    top_parties = sorted(party_seat_counts, key=party_seat_counts.get, reverse=True)[:8]

    # 누락 0 채우기
    for cn in cluster_data:
        for p in top_parties:
            cluster_data[cn].setdefault(p, {r: 0 for r in result_types})

    cluster_vote_data = {
        str(cn): {
            "cluster_num": cn,
            "cluster_keywords": cluster_keywords.get(cn, ""),
            "party_stats": ps,
        }
        for cn, ps in cluster_data.items()
    }

    return {
        "cluster_data": cluster_vote_data,
        "party_names": top_parties,
        "result_types": result_types,
    }


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


# ---- 의원 추천 --------------------------------------------------
MIN_VOTE_COUNT = 3


def _ratio(summary, vote_type):
    total = summary.찬성 + summary.반대 + summary.기권 + summary.불참
    return getattr(summary, vote_type) / total if total else 0


def get_top_members_for_user_clusters(cluster_list, vote_type="찬성"):
    """
    여러 클러스터에서 vote_type 비율이 가장 높은 의원 1명 추천
    (가중 평균: 표결 수 반영)
    """
    candidate_map = defaultdict(lambda: {
        "member": None,
        "cluster_ids": set(),
        "weighted_sum": 0.0,
        "total_votes": 0,
    })

    for cid in cluster_list:
        for s in VoteSummary.objects.filter(cluster=cid).select_related("member"):
            votes = s.찬성 + s.반대 + s.기권 + s.불참
            if votes < MIN_VOTE_COUNT:
                continue
            data = candidate_map[s.member.id]
            data["member"] = s.member
            data["cluster_ids"].add(cid)
            data["weighted_sum"] += _ratio(s, vote_type) * votes
            data["total_votes"] += votes

    if not candidate_map:
        return None

    best = max(
        (
            {
                "member": d["member"],
                "clusters": d["cluster_ids"],
                "score": d["weighted_sum"] / d["total_votes"],
            }
            for d in candidate_map.values() if d["total_votes"]
        ),
        key=lambda x: x["score"],
        default=None,
    )
    if not best:
        return None

    return {
        "id": best["member"].id,
        "name": best["member"].name,
        "party": best["member"].party.party if best["member"].party else "소속없음",
        "ratio": round(best["score"] * 100, 1),
        "cluster": ", ".join(map(str, best["clusters"])),
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

    liked_clusters = {b.cluster for b in bill_list if b.cluster}

    # 클러스터 빈도 및 키워드
    cluster_counts = dict(Counter(liked_clusters))
    cluster_keywords = defaultdict(set)
    for b in bill_list:
        if b.cluster and b.cluster_keyword:
            cluster_keywords[b.cluster].update(
                kw.strip() for kw in b.cluster_keyword.split(",")
            )
    cluster_keywords = {c: ", ".join(sorted(kws)) for c, kws in cluster_keywords.items()}

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
        if liked_ids
        else []
    )

    # 차트 데이터
    cluster_stats_data = get_user_cluster_stats(request.user)

    # 정당 추천
    most_similar, most_opposite = recommend_party_by_interest(request.user)

    # 의원 추천
    rec_support = get_top_members_for_user_clusters(liked_clusters, "찬성")
    rec_oppose  = get_top_members_for_user_clusters(liked_clusters, "반대")

    # 표결 최대 클러스터(시각화용)
    max_clusters = get_max_clusters_for_member(request.user.username)

    return render(request, "my_page.html", {
        "username": request.user.username,
        "liked_bills": bill_list,
        "liked_ids": liked_ids,
        "cluster_counts": cluster_counts,
        "cluster_keywords": cluster_keywords,
        "recommended_bills": recommended_bills,
        "top_similar_clusters": similar_clusters,
        "cluster_stats_data": cluster_stats_data,
        "cluster_data": cluster_stats_data["cluster_data"],
        "party_names": cluster_stats_data["party_names"],
        "result_types": cluster_stats_data["result_types"],
        "most_similar_party": most_similar,
        "most_opposite_party": most_opposite,
        "palette_colors": PALETTE,
        "recommended_support_member": rec_support,
        "recommended_oppose_member":  rec_oppose,
        "max_clusters": max_clusters,
    })
