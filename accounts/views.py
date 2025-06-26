from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from accounts.models import BillLike
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from collections import Counter, defaultdict
from django.db.models import Q
from billview.models import Bill
from geovote.models import Age
from main.models import ClusterKeyword, PartyClusterStats
import json


def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save() # user 생성 및 저장
            return redirect('accounts:login') # 로그인 페이지로 이동
    else:
        form = CustomUserCreationForm()
    context = {'form': form}
    return render(request, 'signup.html', context)

def login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, request.POST)  # request 꼭 넣기
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)  # Django의 login 함수로 세션 발급
            return redirect('home')  # 로그인 성공 시 이동할 곳
    else:
        form = CustomAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout(request):
    auth_logout(request)
    return redirect('home')

# 유사 클러스터 계산
def jaccard_score(set1, set2):
    return len(set1 & set2) / len(set1 | set2) if set1 | set2 else 0

def get_user_cluster_stats(user):
    liked_bills = BillLike.objects.filter(user=user).select_related('bill')
    liked_clusters = set(bill.bill.cluster for bill in liked_bills if bill.bill.cluster is not None)
    if not liked_clusters:
        return {
            'cluster_data': [],
            'party_names': [],
            'party_colors': [],
            'result_types': [],
        }
    
    # Age 조건은 필요에 따라 조절 가능
    age = Age.objects.first()

    # 클러스터 키워드 조회
    keywords_raw = ClusterKeyword.objects.filter(cluster_num__in=liked_clusters)
    cluster_keywords = {}
    for ck in keywords_raw:
        try:
            kw_list = json.loads(ck.keyword_json)
            cluster_keywords[ck.cluster_num] = ', '.join(kw_list)
        except Exception:
            cluster_keywords[ck.cluster_num] = ck.keyword_json

    # 통계 조회 (PartyClusterStats 모델을 기준으로, 필요에 따라 조정)
    stats = PartyClusterStats.objects.filter(
        cluster_num__in=liked_clusters,
        # age=age,  # 필요하면 age 조건 추가
    ).select_related('party')

    party_names = sorted({stat.party.party for stat in stats})
    party_colors = [stat.party.color for stat in stats if stat.party.party in party_names]

    result_types = ['찬성', '반대', '기권', '불참']
    cluster_data = defaultdict(lambda: defaultdict(lambda: {r: 0 for r in result_types}))

    for row in stats:
        party = row.party.party
        cluster = row.cluster_num
        cluster_data[cluster][party] = {
            '찬성': round(row.support_ratio),
            '반대': round(row.oppose_ratio),
            '기권': round(row.abstain_ratio),
            '불참': round(row.absent_ratio),
        }

    # 누락된 정당 0 초기화
    for cluster in cluster_data:
        for party in party_names:
            cluster_data[cluster].setdefault(party, {r: 0 for r in result_types})

    cluster_vote_data_dict = {
        cluster_num: {
            'cluster_num': cluster_num,
            'cluster_keywords': cluster_keywords.get(cluster_num, ''),
            'party_stats': party_stats,
        }
        for cluster_num, party_stats in cluster_data.items()
    }

    return {
        'cluster_data': cluster_vote_data_dict,
        'party_names': party_names,
        'party_colors': party_colors,
        'result_types': result_types,
    }

# my_page 화면
@login_required
def my_page(request):
    # 좋아요 버튼
    liked_bills = BillLike.objects.filter(user=request.user).select_related('bill')
    liked_ids = liked_bills.values_list('bill_id', flat=True)
    bill_list = [like.bill for like in liked_bills]

    # 1) 관심 법안의 클러스터
    cluster_ids = [bill.cluster for bill in bill_list if bill.cluster]
    cluster_counts = Counter(cluster_ids)
    cluster_counts = dict(cluster_counts)


    # 2) 클러스터별 키워드 모으기 (중복 제거)
    cluster_keywords = defaultdict(set)
    for bill in bill_list:
        if bill.cluster is not None and bill.cluster_keyword:
            # 만약 키워드가 콤마 구분이면 분리해서 저장 가능
            keywords = [kw.strip() for kw in bill.cluster_keyword.split(',')]
            for kw in keywords:
                cluster_keywords[bill.cluster].add(kw)
            # 지금은 그냥 통째로 저장
            # cluster_keywords[bill.cluster].add(bill.cluster_keyword.strip())

    # 3) 집합을 콤마로 연결한 문자열로 변환
    for cluster, keywords in cluster_keywords.items():
        cluster_keywords[cluster] = ", ".join(sorted(keywords))

    # 유사도 기반 추천 클러스터
    # 모든 클러스터 키워드 불러오기 (특정 age에 한정 가능)
    all_cluster_keywords = ClusterKeyword.objects.all()

    # keyword_json 직접 파싱해서 set 생성
    full_cluster_keywords = {}
    for ck in all_cluster_keywords:
        if ck.keyword_json:
            # 문자열을 콤마 기준으로 분리하고 공백 제거
            keywords = [kw.strip() for kw in ck.keyword_json.split(',')]
            full_cluster_keywords[ck.cluster_num] = set(keywords)
    user_clusters = set(cluster_counts.keys())

    user_keywords = set()
    for cid in user_clusters:
        user_keywords.update(full_cluster_keywords.get(cid, set()))

    similar_clusters = []
    for cid, keywords in full_cluster_keywords.items():
        if cid in user_clusters:
            continue
        score = jaccard_score(user_keywords, keywords)
        if score > 0:
            similar_clusters.append((cid, score))

    similar_clusters.sort(key=lambda x: x[1], reverse=True)
    top_similar_clusters = similar_clusters[:3]

    recommended_bills = Bill.objects.filter(
        cluster__in=[cid for cid, _ in top_similar_clusters]
    ).exclude(id__in=liked_ids)[:10]

    # 차트 그리기
    cluster_stats_data = get_user_cluster_stats(request.user)

    # 페이지네이션
    paginator = Paginator(bill_list, 5)
    page_obj = paginator.get_page(request.GET.get("page"))
    current = page_obj.number
    total = paginator.num_pages
    start = ((current - 1) // 10) * 10 + 1
    end = min(start + 9, total)
    page_range = range(start, end + 1)

    context = {
        'username': request.user.username,

        'liked_bills': page_obj,
        'liked_ids': list(liked_ids),

        'page_obj': page_obj,
        'page_range': page_range,

        # 클러스터
        'cluster_counts': cluster_counts,
        'cluster_keywords': cluster_keywords, 

        # 추천 법안 리스트 (유사 클러스터 기반)
        'recommended_bills': recommended_bills,
        'top_similar_clusters': top_similar_clusters,

        # 통계 데이터
        'cluster_stats_data': cluster_stats_data,
    }
    return render(request, 'my_page.html', context)