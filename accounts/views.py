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
from django.db.models import Q
from billview.models import Bill
from geovote.models import Age, Member
from main.models import ClusterKeyword, PartyClusterStats, VoteSummary
from geovote.models import Age, Member
from main.models import ClusterKeyword, PartyClusterStats, VoteSummary
import json
from collections import namedtuple
from geovote.views import get_max_clusters_for_member
import logging


PALETTE = [
    '#bef264', '#67e8f9', '#f9a8d4', '#fde68a', '#fdba74',
    '#6ee7b7', '#c3b4fc', '#fda4af', '#5eead4', '#34d399',
    '#f472b6', '#facc15', '#fb7185', '#818cf8', '#38bdf8',
]

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


# 관심 클러스터 차트 데이터
def get_user_cluster_stats(user, cluster_num=None):
    liked_bills = BillLike.objects.filter(user=user).select_related('bill')
    liked_clusters = set(bill.bill.cluster for bill in liked_bills if bill.bill.cluster is not None)
    
    # if cluster_num is None:
    # else:
    #     liked_clusters = set(cluster_num)

    # if not liked_clusters:
    #     return {
    #         'cluster_data': [],
    #         'party_names': [],
    #         'party_colors': [],
    #         'result_types': [],
    #     }, Age.objects.none()

    liked_bills = BillLike.objects.filter(user=user).select_related('bill')


    # 클러스터별 키워드
    keywords_raw      = ClusterKeyword.objects.filter(cluster_num__in=liked_clusters)
    cluster_keywords  = {}
    for ck in keywords_raw:
        try:
            kw_list = json.loads(ck.keyword_json)
            cluster_keywords[ck.cluster_num] = ", ".join(kw_list)
        except Exception:
            cluster_keywords[ck.cluster_num] = ck.keyword_json

    # 통계 조회 (PartyClusterStats 모델을 기준으로, 필요에 따라 조정)
    stats = PartyClusterStats.objects.filter(
        cluster_num__in=liked_clusters,
        # age=age,
    ).select_related('party')

    # 의석수 상위 8개 정당 필터링
    party_seat_counts = {}
    for stat in stats:
        party_name = stat.party.party
        seat_count = getattr(stat.party, 'seat_count', 0)  # seat_count 필드 가정
        party_seat_counts[party_name] = seat_count
    top_parties = sorted(party_seat_counts, key=lambda p: party_seat_counts[p], reverse=True)[:8]

    # party_names = sorted({stat.party.party for stat in stats})
    # party_colors = [stat.party.color for stat in stats if stat.party.party in party_names]

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
        for party in top_parties:
            cluster_data[cluster].setdefault(party, {r: 0 for r in result_types})

    cluster_vote_data_dict = {
        str(cluster_num): {
            "cluster_num":      cluster_num,
            "cluster_keywords": cluster_keywords.get(cluster_num, ""),
            "party_stats":      party_stats,
        }
        for cluster_num, party_stats in cluster_data.items()
    }

    return {
        'cluster_data': cluster_vote_data_dict,
        'party_names': top_parties,
        'result_types': result_types,
    }

# 관심 비슷한 추천 정당
def recommend_party_by_interest(user, age_num=None):
    # 1. 사용자 관심 클러스터 수집
    liked_clusters = BillLike.objects.filter(user=user) \
        .values_list('bill__cluster', flat=True).distinct()
    liked_clusters = [c for c in liked_clusters if c is not None]

    if not liked_clusters:
        return None, None

    # 2. 관심 클러스터에 대한 정당별 표결 통계 조회
    stats = PartyClusterStats.objects.filter(cluster_num__in=liked_clusters)
    if age_num:
        stats = stats.filter(age__number=age_num)

    party_summary = defaultdict(lambda: {
        'party': None,
        'support': [],
        'oppose': [],
        'abstain': [],
        'absent': []
    })

    for row in stats:
        p = row.party.party
        party_summary[p]['party'] = p
        party_summary[p]['support'].append(row.support_ratio)
        party_summary[p]['oppose'].append(row.oppose_ratio)
        party_summary[p]['abstain'].append(row.abstain_ratio)
        party_summary[p]['absent'].append(row.absent_ratio)

    results = []
    for party, data in party_summary.items():
        avg_support = sum(data['support']) / len(data['support'])
        avg_oppose = sum(data['oppose']) / len(data['oppose'])
        avg_abstain = sum(data['abstain']) / len(data['abstain'])
        avg_absent = sum(data['absent']) / len(data['absent'])

        results.append({
            'party': party,
            'support': avg_support,
            'oppose': avg_oppose,
            'abstain': avg_abstain,
            'absent': avg_absent,
        })

    most_similar = max(results, key=lambda x: x['support'], default=None)
    most_oppose = max(results, key=lambda x: x['oppose'], default=None)
    most_abstain = max(results, key=lambda x: x['abstain'], default=None)
    most_absent = max(results, key=lambda x: x['absent'], default=None)

    return most_similar, most_opposite

# 개인별 관심 클러스터 - 의원 클러스터 매칭
def extract_cluster_ids_from_max_clusters(max_clusters):
    """max_clusters에서 cluster_id만 추출"""
    return {
        v['cluster_id']
        for vt, v in max_clusters.items()
        if vt in ['찬성', '반대', '기권', '불참'] and 'cluster_id' in v
    }

def get_top_members_for_user_clusters(user_clusters, limit=5):
    """사용자 관심 클러스터 리스트를 받아서 각 클러스터별 추천 의원 반환"""
    recommended = {}

    for cluster_id in user_clusters:
        summaries = VoteSummary.objects.filter(cluster=cluster_id)\
            .select_related('member')\
            .order_by('-bill_count')[:limit]

        members = [{
            'id': s.member.id,
            'name': s.member.name,
            'party': s.member.party.party if s.member.party else '소속없음',
            'bill_count': s.bill_count,
        } for s in summaries]

        recommended[cluster_id] = members

    return recommended


def get_recommended_members_from_max_clusters(max_clusters, limit=5):
    """여러 클러스터에서 활동량 높은 의원들 추천"""
    cluster_ids = extract_cluster_ids_from_max_clusters(max_clusters)
    return {
        cluster_id: get_top_members_by_cluster(cluster_id, limit)
        for cluster_id in cluster_ids
    }


# my_page 화면
@login_required
def my_page(request):
    # 좋아요 버튼
    liked_bills = BillLike.objects.filter(user=request.user).select_related('bill')
    liked_ids = liked_bills.values_list('bill_id', flat=True)
    bill_list = [like.bill for like in liked_bills]
    liked_clusters = set(bill.cluster for bill in bill_list if bill.cluster is not None)

    # 클러스터 선택: GET 파라미터에서 받되, 기본값은 좋아요 클러스터 중 첫 번째
    cluster_num = request.GET.get('cluster_num')
    if cluster_num:
        try:
            cluster_num = int(cluster_num)
        except ValueError:
            cluster_num = None
    if cluster_num not in liked_clusters:
        cluster_num = next(iter(liked_clusters), None)

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

    recommended_bills = Bill.objects.filter(
        cluster__in=[cid for cid, _ in top_similar_clusters]
    ).exclude(id__in=liked_ids)[:10]
    
    # 관심 법안 표결 차트
    cluster_stats_data = get_user_cluster_stats(request.user, cluster_num)
    # 관심사 비슷한 정당 추천
    most_similar_party, most_opposite_party = recommend_party_by_interest(request.user)

    

    # 차트 그리기
    # cluster_stats_data = get_user_cluster_stats(request.user)

    # # 대수 드롭박스
    # ages =  Age.objects.all().order_by('id')

    # 의원 - 클러스터 추천 연결
    recommended_members = get_top_members_for_user_clusters(liked_clusters, limit=5)


    context = {
        # 기본 정보
        "username":  request.user.username,
        # 좋아요 목록
        "liked_bills": bill_list,
        "liked_ids":   list(liked_ids),
        # 클러스터
        'cluster_counts': cluster_counts,
        'cluster_keywords': cluster_keywords, 

        # 추천 법안 리스트 (유사 클러스터 기반)
        'recommended_bills': recommended_bills,
        'top_similar_clusters': top_similar_clusters,

        # 통계 데이터
        'cluster_stats_data': cluster_stats_data,
        'cluster_data': cluster_stats_data['cluster_data'],
        'party_names': cluster_stats_data['party_names'],
        'result_types': cluster_stats_data['result_types'],

        # 정당 추천
        'party_comparisons': [most_similar, most_opposite],

        # 해시태그 색
        'palette_colors': PALETTE,
        'most_similar_party': most_similar_party,
        'most_opposite_party': most_opposite_party,
        'ages': ages,

        # 의원 매칭
        'recommended_members': recommended_members,
        'max_clusters': user_clusters,
    }
    

    return render(request, 'my_page.html', context)
