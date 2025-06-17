from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe
from django.db.models import Count, Min, Sum, Max, Q, F, FloatField, ExpressionWrapper
from collections import Counter, defaultdict
from geovote.models import Vote, Member, Party, Age
from billview.models import Bill
from main.models import AgeStats, PartyClusterStats, ClusterKeyword, PartyConcentration
from django.http import JsonResponse
import json


result_types = ['찬성', '반대', '기권', '불참']

# 정당별 통계
def get_partyStats_data(congress_num):
    try:
        ages = Age.objects.get(number=congress_num)
    except Age.DoesNotExist:
        return {
            'error': f'{congress_num}대에 해당하는 Age 객체가 없습니다'
            }

    # 인스턴스
    votes = Vote.objects.filter(age__number=congress_num).select_related('member__party')
    age_stats = AgeStats.objects.get(age=ages)

    # 저장할 리스트 생성
    result_types = ['찬성', '반대', '기권', '불참']
    categories = result_types

    # series = []
    # result_data = {r: [] for r in result_types}
    # party_names = []
    # party_colors = []

    # 모든 대수 공통: 멤버 수 기준 상위 8개 정당만 필터링
    top_parties = (
        Member.objects
        .filter(age=ages)
        .values('party', 'party__party', 'party__color')
        .annotate(member_count=Count('id'))
        .order_by('-member_count')[:8]
    )

    top_party_ids = [p['party'] for p in top_parties]
    party_id_to_name_color = {
        p['party']: (p['party__party'], p['party__color'])
        for p in top_parties
    }
    # parties = Party.objects.filter(id__in=top_party_ids)  # 실제 정당 객체 리스트

    # 딕셔너리 매핑
    # party_id_to_name_color = {
    #     p['party']: (p['party__party'], p['party__color'])
    #     for p in top_parties
    # }

    # 표결별 집계
    vote_counts = votes.filter(
        member__party__id__in=top_party_ids
        ).values(
            'member__party', 'result'
        ).annotate(
            count=Count('id')
        )
    # 정당별 총 표결수
    total_counts = votes.filter(
        member__party__id__in=top_party_ids
        ).values(
            'member__party'
        ).annotate(
            total=Count('id')
        )
    # dict 변환
    # party_total_dict = {entry['member__party']: entry['total'] for entry in total_counts}
    # party_result_dict = defaultdict(dict)
    # for entry in vote_counts:
    #     party_id = entry['member__party']
    #     result = entry['result']
    #     count = entry['count']
    #     party_result_dict[party_id][result] = count

    # 정당별 총 표결 수
    total_counts = defaultdict(int)
    party_result_dict = defaultdict(lambda: defaultdict(int))
    for entry in vote_counts:
        party_id = entry['member__party']
        result = entry['result']
        count = entry['count']
        total_counts[party_id] += count
        party_result_dict[party_id][result] += count

    # 결과 구성
    series = []
    party_names = []
    party_colors = []

    # 최종 정당별 시리즈 구성
    for party_id in top_party_ids:
        party_name, color = party_id_to_name_color[party_id]
        total = total_counts[party_id]
        proportions = [
            round(party_result_dict[party_id].get(r, 0) / total * 100, 1) if total else 0
            for r in result_types
        ]
        # proportions = {
        #     r: (party_result_dict[party_id].get(r, 0) / total * 100 if total else 0)
        #     for r in result_types
        # }

        series.append({
            'name': party_name,
            'data': proportions
        })
        party_names.append(party_name)
        party_colors.append(color)

    # 통계 가져오기
    # total_bills = age_stats.total_bills
    # total_parties = age_stats.total_parties
    # male_count = age_stats.male_count
    # female_count = age_stats.female_count
    # female_percent = age_stats.female_percent

    return {
        'party_names': party_names,
        'party_colors': party_colors,
        'series': mark_safe(json.dumps(series)),
        'categories': mark_safe(json.dumps(result_types)),

        'total_votes': sum(total_counts.values()),
        'total_bills': age_stats.total_bills,
        'total_parties': age_stats.total_parties,

        'gender_ratio': {
            'male': age_stats.male_count,
            'female': age_stats.female_count,
            'female_percent': age_stats.female_percent,
        },
    }

# 정당/클러스터별 통계
def get_partyClusterStats_data(congress_num, top_n_clusters=20):
    age = get_object_or_404(Age, number=congress_num)

    # 클러스터별 전체 요약 불러오기
    top_parties = (
        PartyClusterStats.objects
        .filter(age=age)
        .values('party', 'party__party', 'party__color')
        .annotate(member_count=Count('id'))
        .order_by('-member_count')[:8]
    )
    party_names = [p['party__party'] for p in top_parties]
    party_colors = [p['party__color'] for p in top_parties]
    top_party_ids = [p['party'] for p in top_parties]

    # 상위 N개 클러스터 (전체 투표 수 기준)
    top_clusters = (
        PartyClusterStats.objects
        .filter(age=age, party__id__in=top_party_ids)
        .values('cluster_num')
        .annotate(cluster_votes=Sum('total_votes'))
        .order_by('-cluster_votes')[:top_n_clusters]
    )
    top_cluster_nums = [c['cluster_num'] for c in top_clusters]

    # 클러스터별 키워드 매핑
    keywords_raw = ClusterKeyword.objects.filter(age=age, cluster_num__in=top_cluster_nums)
    cluster_keywords = {}
    for ck in keywords_raw:
        try:
            keyword_list = json.loads(ck.keyword_json)
            keyword_display = ', '.join(keyword_list)
        except:
            keyword_display = ck.keyword_json
        cluster_keywords[ck.cluster_num] = keyword_display

    # 정당/클러스터 통계 가져오기
    stats = PartyClusterStats.objects.filter(
        age=age,
        cluster_num__in=top_cluster_nums,
        party__id__in=top_party_ids
    ).select_related('party')

    result_types = ['찬성', '반대', '기권', '불참']
    cluster_data = defaultdict(lambda: defaultdict(lambda: {r: 0 for r in result_types}))

    for row in stats:
        party_name = row.party.party
        cluster = row.cluster_num
        cluster_data[cluster][party_name] = {
            '찬성': round(row.support_ratio),
            '반대': round(row.oppose_ratio),
            '기권': round(row.abstain_ratio),
            '불참': round(row.absent_ratio),
        }

    # 누락된 정당에 대해 0으로 초기화
    for cluster in cluster_data:
        for party in party_names:
            cluster_data[cluster].setdefault(party, {r: 0 for r in result_types})

    # cluster_data 딕셔너리를 템플릿에 맞게 리스트로 변환
    cluster_vote_data_list = []
    for cluster_num, party_stats in cluster_data.items():
        cluster_vote_data_list.append({
            'cluster_num': cluster_num,
            # 'cluster_label': cluster_num,  # 별도 라벨 있으면 수정 가능
            'cluster_keywords': cluster_keywords.get(cluster_num, ''),
            'party_stats': party_stats,  # 필요하면 포함
        })

    return {
        'cluster_data': cluster_vote_data_list,
        'party_names': party_names,
        'party_colors': party_colors,
        'result_types': result_types,
        # 'cluster_keywords': cluster_keywords,
    }

# 양당 점유율/권력 집중도
def get_partyConcentration_data(congress_num):
    # 대수 필터링
    try:
        ages = Age.objects.get(number=congress_num)
    except Age.DoesNotExist:
        return {
            'error': f'{congress_num}대에 해당하는 Age 객체가 없습니다'
        }
    
    data = PartyConcentration.objects.filter(age=ages).order_by('rank')

    party_names = [pc.party.party for pc in data]
    member_counts = [pc.member_count for pc in data]

    # 상위 2개 당
    top2_data = data[:2]
    top2_ratio = sum([pc.seat_share for pc in top2_data])
    hhi = AgeStats.objects.get(age=ages).hhi
    enp = AgeStats.objects.get(age=ages).enp

    top2_datail = [
        {
            'party': pc.party.party,
            'seat_share': round(pc.seat_share, 2),
            'color': pc.party.color,
        }
        for pc in top2_data
    ]

    return {
        'party_names': party_names,
        'member_counts': member_counts,
        'top2_seat_shares': [round(pc.seat_share, 2) for pc in top2_data],
        'top2_ratio': round(top2_ratio, 2),
        'top2_datail': top2_datail,
        'hhi': round(hhi, 4),
        'enp': round(enp, 4),
        'age': ages,
    }

# 시계열 차트
def get_concentration_timeseries():
    age_objs = Age.objects.all().order_by('number')
    
    ages = []
    total_parties = []
    hhi_values = [] # hhi 시계열
    enp_values = [] # enp 시계열
    top2_seat_shares_series = []  # 양당 점유율 시계열

    for age in age_objs:
        try:
            stats = AgeStats.objects.get(age=age)
        except AgeStats.DoesNotExist:
            continue

        top2 = PartyConcentration.objects.filter(age=age).order_by('rank')[:2]
        top2_ratio = sum([pc.seat_share for pc in top2])

        ages.append(f"{age.number}대")
        total_parties.append(stats.total_parties)
        hhi_values.append(round(stats.hhi, 4))
        enp_values.append(round(stats.enp, 4))
        top2_seat_shares_series.append(round(top2_ratio, 2))
    
    return {
        'ages': ages,
        'total_parties': total_parties,
        'hhi_values': hhi_values,
        'enp_values': enp_values,
        'top2_seat_shares_series': top2_seat_shares_series,
    }

# 당별 찬/반 가장 많은 클러스터 무엇인지 차트
def get_top_clusters_by_party_and_stance(age_num, stance='oppose', party_name=None, top_n=2):
    field_name = 'oppose_ratio' if stance == 'oppose' else 'abstain_ratio'
    age = get_object_or_404(Age, number=age_num)

    cluster_keyword_map = {}
    keywords_raw = ClusterKeyword.objects.filter(age=age)
    for ck in keywords_raw:
        try:
            keyword_list = json.loads(ck.keyword_json)
            keyword_display = ', '.join(keyword_list)
        except:
            keyword_display = ck.keyword_json
        cluster_keyword_map[ck.cluster_num] = keyword_display

    stats = PartyClusterStats.objects.filter(age__number=age_num).order_by('party', f'-{field_name}')

    # 상위 7개 정당만 추출하기 위해 정당 리스트 생성
    unique_parties = list(dict.fromkeys(stat.party.party for stat in stats))  # 정당명 순서 유지하며 중복 제거
    top_parties = unique_parties[:7]  # 상위 7개 정당만 사용

    party_cluster_map = defaultdict(list)
    for stat in stats:
        party = stat.party.party
        if party not in top_parties:
            continue
        if len(party_cluster_map[party]) < top_n:
            party_cluster_map[party].append({
                'cluster_num': stat.cluster_num,
                'ratio': getattr(stat, field_name)
            })

    # x축: 전체 unique 클러스터 번호
    unique_cluster_nums = sorted(set(
        c['cluster_num'] for clusters in party_cluster_map.values() for c in clusters
    ))
    cluster_labels = [f'클러스터 {num}' for num in unique_cluster_nums]

    series = []
    for party, clusters in party_cluster_map.items():
        cluster_ratio_map = {c['cluster_num']: c['ratio'] for c in clusters}
        data = [round(cluster_ratio_map.get(num, 0), 1) for num in unique_cluster_nums]
        series.append({
            'name': party,
            'data': data
        })

    keyword_map = {f'클러스터 {num}': cluster_keyword_map.get(num, '') for num in unique_cluster_nums}

    return {
        'categories': cluster_labels,  # x축: 클러스터명 리스트
        'series': series,              # 정당별 시리즈
        'keywords': keyword_map,
        'cluster_nums': unique_cluster_nums  # 드롭박스용으로도 넘겨줌
    }

def get_cluster_options(age_num, top_n=2):
    age = get_object_or_404(Age, number=age_num)

    # 찬성, 반대, 기권 데이터 한꺼번에 준비
    stances = ['oppose', 'abstain']
    field_map = {
        'oppose': 'oppose_ratio',
        'abstain': 'abstain_ratio',
    }

    cluster_keyword_map = {}
    keywords_raw = ClusterKeyword.objects.filter(age=age)
    for ck in keywords_raw:
        try:
            keyword_list = json.loads(ck.keyword_json)
            keyword_display = ', '.join(keyword_list)
        except:
            keyword_display = ck.keyword_json
        cluster_keyword_map[ck.cluster_num] = keyword_display

    # 전체 stats를 먼저 불러와서 상위 7개 정당만 추출
    all_stats = PartyClusterStats.objects.filter(age=age).order_by('party')
    unique_parties = list(dict.fromkeys(stat.party.party for stat in all_stats))
    top_parties = unique_parties[:7]
    
    # 정당별, stance별 top N 클러스터 담을 dict
    party_stance_clusters = defaultdict(lambda: defaultdict(list))

    for stance in stances:
        field_name = field_map[stance]
        stats = PartyClusterStats.objects.filter(age=age).order_by('party', f'-{field_name}')

        for stat in stats:
            party = stat.party.party
            if len(party_stance_clusters[party][stance]) < top_n:
                party_stance_clusters[party][stance].append({
                    'cluster_num': stat.cluster_num,
                    'ratio': getattr(stat, field_name)
                })

    # 옵션 리스트 만들기
    options = []
    for party, stance_map in party_stance_clusters.items():
        for stance, clusters in stance_map.items():
            for c in clusters:
                cluster_num = c['cluster_num']
                keyword = cluster_keyword_map.get(cluster_num, '')
                # 옵션 텍스트
                text = f"{party} - {stance} - 클러스터 {cluster_num} ({keyword})"
                # 옵션 value는 나중에 파싱하기 좋게
                value = f"{party}--{stance}--{cluster_num}"
                options.append({'value': value, 'text': text})

    return options


def top_clusters_api(request):
    age_num = int(request.GET.get('age', 22))
    stance = request.GET.get('stance', 'oppose')
    party_name = request.GET.get('party')

    data = get_top_clusters_by_party_and_stance(age_num, stance, party_name, top_n=2)
    return JsonResponse({'data': data})

# dashboard.html로 보내는 함수
def dashboard(request, congress_num):
    # 대수 필터링
    if congress_num not in [20, 21, 22]: # 유효하지 않은 링크 처리
        raise Http404("Invalid congress num")

    party_data = get_partyStats_data(congress_num)
    cluster_vote_data = get_partyClusterStats_data(congress_num, top_n_clusters=10)
    party_concentration_data = get_partyConcentration_data(congress_num)
    timeseries_data = get_concentration_timeseries()
    oppose_top_cluster = get_top_clusters_by_party_and_stance(congress_num, 'oppose')
    abstain_top_cluster = get_top_clusters_by_party_and_stance(congress_num, 'abstain')

    cluster_options = get_cluster_options(congress_num)

    # AgeStats 정보
    try:
        age = Age.objects.get(number=congress_num)
        age_stats = AgeStats.objects.get(age=age)
    except (Age.DoesNotExist, AgeStats.DoesNotExist):
        raise Http404("해당 대수의 통계 정보가 없습니다")

    # 클러스터 대표 키워드 가져오기
    bills = Bill.objects.filter(age__number=congress_num)
    cluster_keywords_qs = (
        bills
        .values('cluster')
        .annotate(min_id=Min('id'))
        .order_by('cluster')
    )
    # cluster -> 대표 cluster_keyword mapping 만들기
    min_ids = [entry['min_id'] for entry in cluster_keywords_qs]
    min_bills = Bill.objects.filter(id__in=min_ids).values('cluster', 'cluster_keyword')
    
    cluster_keywords = {}
    for b in min_bills:
        keyword_str = b['cluster_keyword']
        try:
            keyword_list = json.loads(keyword_str)
            keyword_display = ', '.join(keyword_list)
        except Exception:
            keyword_display = str(keyword_str)
        cluster_keywords[b['cluster']] = keyword_display

    context = {
        'congress_num': congress_num,
        'party_names': party_data['party_names'],
        'party_colors': party_data['party_colors'],
        'series': party_data['series'],
        'categories': party_data['categories'],

        'total_votes': party_data['total_votes'],
        'total_bills': party_data['total_bills'],
        'total_parties': party_data['total_parties'],
        'gender_ratio': party_data['gender_ratio'],

        'cluster_vote_data': cluster_vote_data['cluster_data'],  # 핵심 차트 데이터
        'cluster_categories': cluster_vote_data['result_types'],           # x축 범례 (찬성/반대/기권/불참)
        'cluster_party_names': cluster_vote_data['party_names'],         # 정당 이름
        'cluster_party_colors': cluster_vote_data['party_colors'],       # 정당 색상 hex
        # 'cluster_keywords': cluster_vote_data['cluster_keywords'],
        # 'cluster_nums': list(cluster_vote_data['cluster_keywords'].keys()),

        # 정당 집중도 관련 데이터 추가
        'party_concentration_names': party_concentration_data.get('party_names', []),
        'party_concentration_member_counts': party_concentration_data.get('member_counts', []),
        'party_concentration_vote_supports': party_concentration_data.get('vote_supports', []),
        'party_concentration_top2_seat_shares': party_concentration_data.get('top2_seat_shares', []),
        'party_concentration_top2_ratio': party_concentration_data.get('top2_ratio'),
        'party_concentration_top2_datail': party_concentration_data.get('top2_datail'),
        'party_concentration_hhi': party_concentration_data.get('hhi'),
        'party_concentration_enp': party_concentration_data.get('enp'),
        'party_concentration_age': party_concentration_data.get('age'),

        # 시계열
        'timeseries_data_age': timeseries_data['ages'],
        'timeseries_data_total_parties': timeseries_data['total_parties'],
        'timeseries_data_hhi': timeseries_data['hhi_values'],
        'timeseries_data_enp': timeseries_data['enp_values'],
        'timeseries_data_top2_ratio': timeseries_data['top2_seat_shares_series'],

        # 정당별 탑 클러스터
        'oppose_cluster_categories': oppose_top_cluster['categories'],
        'oppose_cluster_series': oppose_top_cluster['series'],
        'oppose_cluster_keywords': oppose_top_cluster['keywords'],

        'abstain_cluster_categories': abstain_top_cluster['categories'],
        'abstain_cluster_series': abstain_top_cluster['series'],
        'abstain_cluster_keywords': abstain_top_cluster['keywords'],

        'cluster_options': cluster_options,
    }

    return render(request, 'dashboard.html', context)