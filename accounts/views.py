# Django_lawRadar/accounts/views.py
# ────────────────────────────────────────────────────────────────
#  accounts 앱: 회원/인증, 마이페이지, 추천 로직을 모두 담은 뷰
#  (아이디 기반 비밀번호 재설정 + 이메일→아이디 찾기 포함)
# ────────────────────────────────────────────────────────────────
from collections import Counter, defaultdict
import json
import logging
from collections import Counter, defaultdict

from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.db.models import Max
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, UpdateView

from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    DirectPasswordResetForm,   # 아이디 기반 비밀번호 재설정
    UpdateUsernameForm,        # 사용자 이름 수정
    FindUsernameForm,          # 이메일로 아이디 찾기
)

from accounts.models import BillLike
from billview.models import Bill
from geovote.models import Age, Member, Party, Vote
from main.models import ClusterKeyword, PartyClusterStats, VoteSummary
from geovote.views import get_max_clusters_for_member
from types import SimpleNamespace


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
    """회원가입"""
    form = CustomUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:login")
    return render(request, "signup.html", {"form": form})


def login(request):
    """로그인 (username + password)"""
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
# 2-A. 아이디 입력 + 즉시 비밀번호 재설정
# ──────────────────────────────────────────────
class DirectPasswordResetView(FormView):
    """
    아이디(username)와 새 비밀번호 두 칸을 받아
    인증 메일 없이 즉시 비밀번호를 변경한다.
    """
    form_class    = DirectPasswordResetForm
    template_name = "login.html"            # login.html 내부 분기 사용
    success_url   = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


def password_reset_complete(request):
    """비밀번호 변경 완료 화면"""
    return render(request, "login.html")

# ──────────────────────────────────────────────
# 2-B. 이메일 → 아이디(username) 찾기
# ──────────────────────────────────────────────
def find_username(request):
    """
    가입한 이메일을 입력하면 연결된 아이디(username)를 보여 준다.
    """
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
    """현재 로그인한 사용자의 username(로그인 ID) 수정"""
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
    """두 키워드 집합의 Jaccard 유사도"""
    return len(set1 & set2) / len(set1 | set2) if (set1 | set2) else 0


def get_user_cluster_stats(user, cluster_num=None):
    """
    사용자가 좋아요한 법안의 클러스터별 표결 통계·키워드
    => 차트에서 바로 쓸 JSON 형태로 반환
    """
    liked_bills = BillLike.objects.filter(user=user).select_related("bill")
    liked_clusters = {b.bill.cluster for b in liked_bills if b.bill.cluster}

    # 클러스터 키워드
    keywords_raw = ClusterKeyword.objects.filter(cluster_num__in=liked_clusters)
    cluster_keywords = {}
    for ck in keywords_raw:
        try:
            cluster_keywords[ck.cluster_num] = ", ".join(json.loads(ck.keyword_json))
        except Exception:
            cluster_keywords[ck.cluster_num] = ck.keyword_json

    # 표결 통계
    stats = PartyClusterStats.objects.filter(cluster_num__in=liked_clusters).select_related("party")

    # 의석수 상위 8개 정당
    seat_map = {s.party.party: getattr(s.party, "seat_count", 0) for s in stats}
    top_parties = sorted(seat_map, key=seat_map.get, reverse=True)[:8]
    stats = PartyClusterStats.objects.filter(
        cluster_num__in=liked_clusters
    ).select_related("party")

    result_types = ["찬성", "반대", "기권", "불참"]
    cluster_data = defaultdict(lambda: defaultdict(lambda: {r: 0 for r in result_types}))

    for row in stats:
        cluster_data[row.cluster_num][row.party.party] = {
            "찬성": round(row.support_ratio),
            "반대": round(row.oppose_ratio),
            "기권": round(row.abstain_ratio),
            "불참": round(row.absent_ratio),
    cluster_data = defaultdict(lambda: defaultdict(lambda: {r: 0 for r in result_types}))

    # 클러스터별로 실제 통계가 존재하는 정당 추리기
    cluster_to_parties = defaultdict(set)
    party_seat_counts = {}

    for stat in stats:
        cluster = stat.cluster_num
        party_name = stat.party.party
        seat_count = getattr(stat.party, 'seat_count', 0)

        cluster_to_parties[cluster].add(party_name)
        party_seat_counts[party_name] = seat_count

        cluster_data[cluster][party_name] = {
            "찬성": round(stat.support_ratio),
            "반대": round(stat.oppose_ratio),
            "기권": round(stat.abstain_ratio),
            "불참": round(stat.absent_ratio),
        }

    # 누락 0 채움
    for cn in cluster_data:
        for p in top_parties:
            cluster_data[cn].setdefault(p, {r: 0 for r in result_types})
    top_parties_per_cluster = {
        cluster: sorted(
            cluster_to_parties[cluster],
            key=lambda p: party_seat_counts.get(p, 0),
            reverse=True
        )[:8]
        for cluster in cluster_to_parties
    }

    for cluster in cluster_data:
        for party in top_parties_per_cluster.get(cluster, []):
            cluster_data[cluster].setdefault(
                party, {r: 0 for r in result_types}
            )
    
    all_top_parties = set()
    for parties in top_parties_per_cluster.values():
        all_top_parties.update(parties)

    top_parties = sorted(
        all_top_parties, key=lambda p: party_seat_counts.get(p, 0), reverse=True
    )

    # for cluster in cluster_data:
    # for party in top_parties_per_cluster.get(cluster, []):
    #     cluster_data[cluster].setdefault(
    #         party, {r: 0 for r in result_types}
    #     )

    # 의석수 상위 8개 정당
    # party_seat_counts = {
    #     stat.party.party: getattr(stat.party, "seat_count", 0) for stat in stats
    # }
    # top_parties = sorted(
    #     party_seat_counts, key=party_seat_counts.get, reverse=True
    # )[:8]

    # result_types = ["찬성", "반대", "기권", "불참"]
    # cluster_data = defaultdict(
    #     lambda: defaultdict(lambda: {r: 0 for r in result_types})
    # )

    # for row in stats:
    #     cluster_data[row.cluster_num][row.party.party] = {
    #         "찬성": round(row.support_ratio),
    #         "반대": round(row.oppose_ratio),
    #         "기권": round(row.abstain_ratio),
    #         "불참": round(row.absent_ratio),
    #     }

    # 누락된 정당은 0으로 채움
    # for cluster in cluster_data:
    #     for party in top_parties:
    #         cluster_data[cluster].setdefault(
    #             party, {r: 0 for r in result_types}
    #         )

    cluster_data = dict(cluster_data)

    cluster_vote_data_dict = {
        str(cluster_id): {
            "cluster_num": cluster_id,
            "cluster_keywords": cluster_keywords.get(cluster_id, ""),
            "party_stats": {k: dict(v) for k, v in party_stats.items()},
        }
        for cluster_id, party_stats in cluster_data.items()
    }

    return {
        "cluster_data": {
            str(cn): {
                "cluster_num": cn,
                "cluster_keywords": cluster_keywords.get(cn, ""),
                "party_stats": ps,
            }
            for cn, ps in cluster_data.items()
        },
        "party_names": top_parties,
        "result_types": result_types,
    }


def recommend_party_by_interest(user, age_num=None):
    """
    좋아요한 클러스터를 기반으로
    친화도 가장 높은/낮은 정당 한 곳씩 추천
    """
    liked_clusters = (
        BillLike.objects.filter(user=user)
        .values_list("bill__cluster", flat=True)
        .distinct()
    )
    liked_clusters = [c for c in liked_clusters if c]
    if not liked_clusters:
        return None, None

    stats = PartyClusterStats.objects.filter(cluster_num__in=liked_clusters)
    if age_num:
        stats = stats.filter(age__number=age_num)

    summary = defaultdict(lambda: {"color": None, "support": [], "oppose": [],
                                   "abstain": [], "absent": []})
    for s in stats:
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
            results.append({
                "party": p,
                "color": d["color"],
                "support": sum(d["support"]) / cnt,
                "oppose": sum(d["oppose"]) / cnt,
                "abstain": sum(d["abstain"]) / cnt,
                "absent": sum(d["absent"]) / cnt,
            })

    most_similar  = max(results, key=lambda x: x["support"], default=None)
    most_opposite = max(results, key=lambda x: x["oppose"],  default=None)
    return most_similar, most_opposite

# ――― 의원 추천 보조 ─―――――――――――――――――――――――――――――――――
MIN_VOTE_COUNT = 3


def get_ratio(summary, vote_type):
    total = summary.찬성 + summary.반대 + summary.기권 + summary.불참
    return getattr(summary, vote_type) / total if total else 0


def get_top_members_for_user_clusters(cluster_list, vote_type="찬성"):
    """
    주어진 클러스터 집합에서 vote_type 비율이 가장 높은 의원 1명 추천
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

            ratio = get_ratio(s, vote_type)
            data = candidate_map[s.member.id]
            data["member"] = s.member
            data["cluster_ids"].add(cid)
            data["weighted_sum"] += ratio * votes
            data["total_votes"] += votes

    scored = []
    for data in candidate_map.values():
        if data["total_votes"]:
            scored.append({
                "member": data["member"],
                "clusters": list(data["cluster_ids"]),
                "score": data["weighted_sum"] / data["total_votes"],
            })

    if not scored:
        return None

    top = max(scored, key=lambda c: c["score"])
    return {
        "id": top["member"].id,
        "name": top["member"].name,
        "party": top["member"].party.party if top["member"].party else "소속없음",
        "ratio": round(top["score"] * 100, 1),
        "cluster": ", ".join(map(str, top["clusters"])),
    }

# ──────────────────────────────────────────────
# 5. 마이페이지
# ──────────────────────────────────────────────
@login_required
def my_page(request):
    # ① 좋아요한 법안 목록
    liked_ids = list(
        BillLike.objects.filter(user=request.user).values_list("bill_id", flat=True)
    )
    bill_list = (
        Bill.objects.filter(id__in=liked_ids)
        .annotate(latest_vote_date=Max("vote__date"))
        .prefetch_related("vote_set")
    )

    liked_clusters = {b.cluster for b in bill_list if b.cluster}

    # ② 클러스터 빈도
    cluster_counts = dict(Counter([b.cluster for b in bill_list if b.cluster]))

    # ③ 키워드 집계(중복 제거)
    cluster_keywords = defaultdict(set)
    for b in bill_list:
        if b.cluster and b.cluster_keyword:
            cluster_keywords[b.cluster].update(
                kw.strip() for kw in b.cluster_keyword.split(",")
            )
    cluster_keywords = {c: ", ".join(sorted(kws)) for c, kws in cluster_keywords.items()}

    # ④ 유사 클러스터 기반 추천 법안
    full_kw = {
        ck.cluster_num: set(k.strip() for k in ck.keyword_json.split(",") if k.strip())
        for ck in ClusterKeyword.objects.all() if ck.keyword_json
    }
    user_kw = {k for cid in cluster_counts for k in full_kw.get(cid, set())}
    similar_clusters = sorted(
        [(cid, jaccard_score(user_kw, kw)) for cid, kw in full_kw.items()
         if cid not in cluster_counts],
        key=lambda x: x[1], reverse=True
    )[:3]

    recommended_bills = (
        Bill.objects.filter(cluster__in=[cid for cid, _ in similar_clusters])
        .exclude(id__in=liked_ids)[:10]
        if liked_ids else []
    )

    # ⑤ 차트용 통계
    cluster_stats_data = get_user_cluster_stats(request.user)

    # ⑥ 정당 추천
    most_similar, most_opposite = recommend_party_by_interest(request.user)

    # ⑦ 의원 추천
    rec_support = get_top_members_for_user_clusters(liked_clusters, "찬성")
    rec_oppose  = get_top_members_for_user_clusters(liked_clusters, "반대")

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
    })
        # 의원 추천
        "max_clusters": max_clusters,
        "recommended_support_member": recommended_support_members,
        "recommended_oppose_member": recommended_oppose_members,
    }
    return render(request, "my_page.html", context)
