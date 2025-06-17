from django.db.models import Q, Count, Max, Subquery, OuterRef
from django.core.paginator import Paginator
from collections import defaultdict, Counter
from django.shortcuts import render
from billview.models import Bill
from geovote.models import Vote
import logging, re, random
from django.http import JsonResponse
from django.core.cache import cache
from django.db.models.functions import Random
from .models import VoteSummary

logger = logging.getLogger(__name__)

# 노드 json 데이터
def cluster_keywords_json(request):
    # 1) 캐시에서 데이터 꺼내기 (키는 'cluster_keywords_data')
    cached = cache.get('cluster_keywords_data')
    if cached:
        return JsonResponse(cached, safe=False)
    
    # 캐시에 없으면 DB에서 쿼리 수행
    qs = (
        Bill.objects
        .exclude(cluster_keyword__isnull=True)
        .exclude(cluster_keyword__exact='')
        .values('cluster', 'cluster_keyword')
        .annotate(
            num_bills=Count('id', distinct=True),
            latest_passed_date=Max('vote__date')
        )
        .filter(num_bills__gt=1)
        .order_by(Random())
    )

    qs_list = list(qs[:300])

    # 상위 100개 랜덤 샘플링
    sample_size = 100
    sorted_qs = sorted(qs_list, key=lambda x: x['num_bills'], reverse=True)
    sampled_qs = random.sample(qs_list, min(len(qs_list), sample_size))

    # json 직렬화
    result = []
    for row in sampled_qs:
        result.append({
            'cluster_index': row['cluster'],
            'keyword': row['cluster_keyword'],
            'num_bills': row['num_bills'],
            'latest_passed_date': row['latest_passed_date'].isoformat() if row['latest_passed_date'] else None,
            'url': f"/cardnews/cluster/{row['cluster']}/",
        })

    # 5) 캐시에 저장 (10분 = 600초)
    cache.set('cluster_keywords_data', result, 60 * 10)

    return JsonResponse(result, safe=False)

# 노드 렌더링
def cluster_galaxy_view(request):
    return render(request, 'home.html')

def home(request):
    # 클러스터와 키워드 조회, 유효한 숫자 클러스터만
    clusters = Bill.objects.filter(
        cluster__isnull=False,
        cluster__gt=0
    ).values('cluster', 'cluster_keyword').distinct().order_by('cluster')
    clusters = [
        {'cluster': c['cluster'], 'keyword': c['cluster_keyword'] or '키워드 없음'}
        for c in clusters if isinstance(c['cluster'], int) and c['cluster'] > 0
    ]
    logger.info(f"Clusters: {clusters}")
    if not clusters:
        logger.warning("No valid clusters found in database")
    return render(request, 'home.html', {'clusters': clusters})


def aboutUs(request):
    return render(request, 'aboutUs.html')

def search(request):
    query = request.GET.get('q', '')
    results = []
    page_obj = None
    page_range = None #
    cluster_keyword_set = set()
    cluster_to_keywords = defaultdict(set)

    if query:
        # 검색 해당 법안 고르기
        matching_bills = Bill.objects.filter(
            Q(title__icontains=query) |
            Q(cleaned__icontains=query) |
            Q(summary__icontains=query) |
            Q(cluster_keyword__icontains=query)
        )

        # 개정횟수 연산
        label_counts = (
            matching_bills
            .exclude(label__isnull=True)
            .values('label')
            .annotate(count=Count('id'))
        )
        label_counts = {item['label']: item['count'] for item in label_counts}

        # 유니크 키워드 추출
        for bill in matching_bills:
            if bill.cluster_keyword and bill.cluster is not None:
                keywords = [kw.strip() for kw in bill.cluster_keyword.strip().split(',')]
                for kw in keywords:
                    kw = kw.strip()
                    if kw:
                        cluster_to_keywords[bill.cluster].add(kw)
        
        # 클러스터 번호별 키워드 문자열 만들기
        cluster_keywords_dict = {
            cluster: ", ".join(sorted(keywords)) for cluster, keywords in cluster_to_keywords.items()
            }

        # 메인 쿼리
        results = Bill.objects.filter(
            Q(title__icontains=query) |
            # Q(cleaned__icontains=query) |
            Q(summary__icontains=query) |
            Q(cluster_keyword__icontains=query),
            id__in=Subquery(
                Bill.objects.filter(
                    label=OuterRef('label')
                    ).order_by('-bill_number').values('id')[:1])
        ).annotate(
            last_vote_date=Max('vote__date')
        ).order_by('-bill_number')
        total_results_count = results.count() # result 개수

        # 클러스터별 빈도 계산
        cluster_counter = Counter()
        for bill in results:
            if bill.cluster:
                cluster_counter[bill.cluster] += 1

        # 파스텔톤
        # color_palette = [
        #     "#F7CAC9", "#A8DADC", "#FFE5B4", "#BFD8B8", "#D6CDEA",
        #     "#F3E9D2", "#C5DDE8", "#F9E2AE", "#E2CFC3", "#B0A8B9",
        #     "#FADADD", "#E0BBE4", "#FFECB3", "#D4E157", "#AED9E0",
        #     "#FCD5CE", "#D1C4E9", "#FFF9C4", "#F8BBD0", "#C8E6C9",
        #     "#EFD3D7", "#CDEDF6", "#FFF5BA", "#D5AAFF", "#FFE1E1",
        #     "#D0F0C0", "#F0D9FF", "#FEEBCB", "#E8EAF6", "#F2D7EE",
        #     "#D3E4CD", "#F6DFEB", "#C2ECEF", "#FFDFD3"
        #     ]

        # treeMap 팔레트
        color_palette = [
            '#bef264', '#67e8f9', '#f9a8d4', '#fde68a', '#fdba74',
            '#6ee7b7', '#c3b4fc', '#fda4af',
            # 추가
            '#5eead4', '#34d399', '#f472b6', '#facc15', '#fb7185', '#818cf8', '#38bdf8'
            ]


        random.shuffle(color_palette)  # 랜덤 섞기

        # 클러스터 ID 리스트
        cluster_ids = list({bill.cluster for bill in results})  # 의안에서 클러스터 id 수집

        # 클러스터별 색상 매핑
        cluster_color_map = {}
        for i, cid in enumerate(cluster_ids):
            cluster_color_map[cid] = color_palette[i % len(color_palette)]

        top_clusters = []
        for i, (cluster_id, _) in enumerate(cluster_counter.most_common(2)):  # 상위 2개 클러스터
            keywords_str = cluster_keywords_dict.get(cluster_id, "")
            if keywords_str:
                keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                color = color_palette[i % len(color_palette)]
                top_clusters.append({
                    'cluster_id': cluster_id,
                    'keywords': keywords,
                    'color': color,
                    })
        
        # 라벨 매핑
        for bill in results:
            bill.label_count = label_counts.get(bill.label, '-')
            words = bill.title.split()
            if len(words) > 4:
                # 1~4번째 단어는 그대로, 5번째 단어부터는 줄바꿈해서 붙임
                first_line = " ".join(words[:5])
                second_line = " ".join(words[5:])
                bill.title_custom = first_line + "<br>" + second_line
            else:
                bill.title_custom = bill.title
        
        # label_count 기준으로 results 정렬 (내림차순)
        results = sorted(results, key=lambda b: label_counts.get(b.label, 0), reverse=True)


        # 클러스터별 색상 지정
        # color_palette = [
        #     "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        #     "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        #     "#bcbd22", "#17becf"
        #     ]
        # cluster_ids = [cluster_id for cluster_id, _ in top_clusters]
        # cluster_colors = {}
        # for i, cid in enumerate(cluster_ids):
        #     cluster_colors[cid] = color_palette[i % len(color_palette)]

        # 페이지네이션----
        paginator = Paginator(results, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        current_page = page_obj.number
        total_pages = paginator.num_pages
        max_page_buttons = 10

        group = (current_page - 1) // max_page_buttons
        start_page = group * max_page_buttons + 1
        end_page = min(start_page + max_page_buttons - 1, total_pages)
        page_range = range(start_page, end_page + 1)
        
    else:
        total_results_count = 0 # 검색어 없으면 0개
        cluster_keywords = []
        
    context = {
        'query': query,
        'page_obj': page_obj,
        'page_range': page_range,
        'total_results_count': total_results_count,
        'cluster_keywords_dict': cluster_keywords_dict,

        'top_clusters': top_clusters,
        # 'cluster_colors': cluster_colors,
        'cluster_color_map': cluster_color_map,
    }
    return render(request, 'search.html', context)

# 국회의원 표결 정보 데이터 연산

def calculate_votesummary(member_name):
    # 1. 해당 의원의 모든 투표 정보를 클러스터별로 집계
    votes = Vote.objects.filter(member__name=member_name)\
        .values('bill__cluster', 'result')\
        .annotate(count=Count('id'))

    # 2. 클러스터 목록 추출
    clusters = set(v['bill__cluster'] for v in votes if v['bill__cluster'] is not None)

    # 3. cluster -> keyword 매핑 사전 생성
    cluster_keywords = {}
    bill_keywords = (
        Bill.objects
        .filter(cluster__in=clusters)
        .exclude(cluster_keyword__isnull=True)
        .exclude(cluster_keyword__exact='')
        .values('cluster', 'cluster_keyword')
    )
    for b in bill_keywords:
        cluster = b['cluster']
        keyword = b['cluster_keyword']
        # 한 클러스터에 여러 키워드가 있을 수 있는데, 첫 번째만 사용 (가장 오래된/대표 키워드)
        if cluster not in cluster_keywords and not keyword.isdigit():
            cluster_keywords[cluster] = keyword
    # 키워드 없는 클러스터 처리
    for cluster in clusters:
        if cluster not in cluster_keywords:
            cluster_keywords[cluster] = "알 수 없음"

    # 4. 클러스터별 전체 법안 개수 계산
    cluster_bill_counts = {
        c: Bill.objects.filter(cluster=c).count() for c in clusters
    }

    # 5. 클러스터별 투표 결과 집계
    cluster_summary = {c: {'찬성': 0, '반대': 0, '기권': 0, '불참': 0} for c in clusters}
    for vote in votes:
        cluster = vote['bill__cluster']
        result = vote['result']
        if result not in cluster_summary[cluster]:
            result = '기권'
        cluster_summary[cluster][result] += vote['count']

    # 6. 기존 VoteSummary 삭제 후 새로운 데이터 저장
    VoteSummary.objects.filter(member_name=member_name).delete()
    for cluster in clusters:
        summary = cluster_summary[cluster]
        VoteSummary.objects.create(
            member_name=member_name,
            cluster=cluster,
            cluster_keyword=cluster_keywords.get(cluster, "알 수 없음"),
            bill_count=cluster_bill_counts.get(cluster, 1),
            찬성=summary['찬성'],
            반대=summary['반대'],
            기권=summary['기권'],
            불참=summary['불참'],
        )
