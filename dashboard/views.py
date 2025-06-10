from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe
from django.db.models import Count, Min, Sum, Q, F, FloatField, ExpressionWrapper
from collections import Counter, defaultdict
from geovote.models import Vote, Member, Party, Age
from billview.models import Bill
from main.models import AgeStats, PartyClusterStats, ClusterKeyword, PartyConcentration
import json

# 정당별 통계
def get_partyStats_data(congress_num):
    try:
        ages = Age.objects.get(number=congress_num)
    except Age.DoesNotExist:
        return {
            'error': f'{congress_num}대에 해당하는 Age 객체가 없습니다'
            }

    # 인스턴스
    votes = Vote.objects.filter(age__number=congress_num).select_related('member__party', 'bill')
    age_stats = AgeStats.objects.get(age=ages)

    # 저장할 리스트 생성
    result_types = ['찬성', '반대', '기권', '불참']
    series = []
    result_data = {r: [] for r in result_types}
    party_names = []
    party_colors = []

    # 카테고리는 표결 결과 (y축)
    categories = result_types

    # 모든 대수 공통: 멤버 수 기준 상위 8개 정당만 필터링
    top_parties = (
        Member.objects
        .filter(age=ages)
        .values('party', 'party__party', 'party__color')
        .annotate(member_count=Count('id'))
        .order_by('-member_count')[:8]
    )

    top_party_ids = [p['party'] for p in top_parties]
    parties = Party.objects.filter(id__in=top_party_ids)  # 실제 정당 객체 리스트

    # 딕셔너리 매핑
    party_id_to_name_color = {
        p['party']: (p['party__party'], p['party__color'])
        for p in top_parties
    }

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
    party_total_dict = {entry['member__party']: entry['total'] for entry in total_counts}
    party_result_dict = defaultdict(dict)
    for entry in vote_counts:
        party_id = entry['member__party']
        result = entry['result']
        count = entry['count']
        party_result_dict[party_id][result] = count

    # 최종 정당별 시리즈 구성
    for party_id in top_party_ids:
        party_name, color = party_id_to_name_color[party_id]
        total = party_total_dict.get(party_id, 0)

        proportions = {
            r: (party_result_dict[party_id].get(r, 0) / total * 100 if total else 0)
            for r in result_types
        }

        series.append({
            'name': party_name,
            'data': [round(proportions[r], 1) for r in result_types]
        })
        party_names.append(party_name)
        party_colors.append(color)

    # 통계 가져오기
    total_bills = age_stats.total_bills
    total_parties = age_stats.total_parties
    male_count = age_stats.male_count
    female_count = age_stats.female_count
    female_percent = age_stats.female_percent

    return {
        'party_names': party_names,
        'party_colors': party_colors,
        'series': mark_safe(json.dumps(series)),
        'categories': mark_safe(json.dumps(categories)),

        'total_votes': votes.count(),
        'total_bills': total_bills,
        'total_parties': total_parties,

        'gender_ratio': {
            'male': male_count,
            'female': female_count,
            'female_percent': female_percent,
        },
    }

# 정당/클러스터별 통계
def get_partyClusterStats_data(congress_num, top_n_clusters=20):
    age = get_object_or_404(Age, number=congress_num)
    votes = Vote.objects.filter(age=age).select_related('member__party', 'bill')

    # 상위 정당 목록 (정당 이름으로 정렬)
    top_parties = (
        Member.objects
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

    return {
        'cluster_data': dict(cluster_data),
        'party_names': party_names,
        'party_colors': party_colors,
        'result_types': result_types,
        'cluster_keywords': cluster_keywords,
    }

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
    # vote_supports = [round(pc.vote_support_ratio, 2) for pc in data]

    total_members = sum(member_counts)

    # 상위 2개 당
    top2 = data[:2]
    top2_member_counts = [pc.member_count for pc in top2]
    top2_seat_shares = [m / total_members * 100 for m in top2_member_counts]

    # 상위 2당 점유율 합
    top2_ratio = sum(top2_seat_shares)

    # 상위 2당 찬성률 평균 (필요하면)
    top2_vote_support_avg = sum(pc.vote_support_ratio for pc in top2) / len(top2) if len(top2) == 2 else 0

    # 전체 권력 집중도(HHI)
    hhi = sum((share / 100) ** 2 for share in top2_seat_shares)

    return {
        'party_names': party_names,
        'member_counts': member_counts,
        # 'vote_supports': vote_supports,
        'top2_seat_shares': top2_seat_shares,
        'top2_ratio': round(top2_ratio, 2),
        'hhi': round(hhi, 4),
        'age': ages,
    }

# def get_gender_vote_data():
#     # 성별/클러스터별 찬반 투표 수 계산
#     gender_results = (
#         Vote.objects
#         .values('member__gender', 'bill__cluster', 'bill__cluster_keyword', 'result')
#         .annotate(count=Count('id'))
#     )

#     # cluster 번호 → keyword 문자열 매핑
#     cluster_keyword_map = {}
#     cluster_votes = {}

#     # 남녀 구분해 정리
#     # gender_stats = {'남': {}, '여': {}}
#     for row in gender_results:
#         gender = row['member__gender']
#         cluster = row['bill__cluster']
#         keyword_raw = row['bill__cluster_keyword']
#         result = row['result']
#         count = row['count']

#         # 예외 처리
#         if cluster is None:
#             continue
        
#         # keyword 문자열 처리
#         if cluster not in cluster_keyword_map:
#             try:
#                 keyword_list = json.loads(keyword_raw)
#                 keyword = ', '.join(keyword_list)
#             except Exception:
#                 keyword = str(keyword_raw)
#             cluster_keyword_map[cluster] = keyword

#         # 클러스터별 성별 찬반 집계
#         cluster_data = cluster_votes.setdefault(cluster, {'남': {'찬성': 0, '반대': 0}, '여': {'찬성': 0, '반대': 0}})
#         if gender in cluster_data and result in cluster_data[gender]:
#             cluster_data[gender][result] += count
        
#     # 성별 찬성률 차이 계산
#     divergence_data = []
#     for cluster, gender_data in cluster_votes.items():
#         남찬성 = gender_data['남']['찬성']
#         남반대 = gender_data['남']['반대']
#         여찬성 = gender_data['여']['찬성']
#         여반대 = gender_data['여']['반대']

#         남총 = 남찬성 + 남반대
#         여총 = 여찬성 + 여반대

#         if 남총 == 0 or 여총 == 0:
#             continue

#         남찬성률 = 남찬성 / 남총 * 100
#         여찬성률 = 여찬성 / 여총 * 100
#         찬성_차이 = abs(남찬성률 - 여찬성률)

#         남반대률 = 남반대 / 남총 * 100
#         여반대률 = 여반대 / 여총 * 100
#         반대_차이 = abs(남반대률 - 여반대률)

#         # 의견 대립되는 경우만 필터링: 서로 반대 방향인지 체크 (한 쪽은 50 이상, 다른 쪽은 50 이하)
#         찬성_갈등 = (남찬성률 >= 50 and 여찬성률 < 50) or (남찬성률 < 50 and 여찬성률 >= 50)
#         반대_갈등 = (남반대률 >= 50 and 여반대률 < 50) or (남반대률 < 50 and 여반대률 >= 50)

#         # 의견이 갈리지 않은 경우는 제외
#         if not (찬성_갈등 or 반대_갈등):
#             continue
#         # 갈등 = (찬성_차이 >= 30) or (반대_차이 >= 30)
#         # if not 갈등:
#         #     continue

#         divergence_data.append({
#             'cluster_num': cluster, # 클러스터 번호
#             'cluster': cluster_keyword_map.get(cluster, f'클러스터 {cluster}'), # 클러스터 키워드 문자열
#             '남성_찬성률': round(남찬성률, 1),
#             '여성_찬성률': round(여찬성률, 1),
#             '찬성_차이': round(찬성_차이, 1),

#             '남성_반대률': round(남반대률, 1),
#             '여성_반대률': round(여반대률, 1),
#             '반대_차이': round(반대_차이, 1)
#         })

#     # 차이 큰 순으로 정렬
#     return divergence_data

# def get_party_cluster_highlight():
#     # 전체 클러스터별 평균 찬성률
#     total_cluster_stats = (
#         Vote.objects.values('bill__cluster')
#         .annotate(
#             total=Count('id'),
#             agree=Count('id', filter=Q(result='찬성'))
#         )
#         .annotate(avg_rate=ExpressionWrapper(F('agree') * 100.0 / F('total'), output_field=FloatField()))
#     )
#     cluster_avg = {stat['bill__cluster']: stat['avg_rate'] for stat in total_cluster_stats}

#     # 정당별 클러스터 찬성률
#     party_cluster_stats = (
#         Vote.objects.values('member__party__party', 'bill__cluster')
#         .annotate(
#             total=Count('id'),
#             agree=Count('id', filter=Q(result='찬성'))
#         )
#         .annotate(rate=ExpressionWrapper(F('agree') * 100.0 / F('total'), output_field=FloatField()))
#     )

#     # 편차 계산 / 정당별 상위 5개 클러스터 필터링
#     party_diffs = defaultdict(list)
#     for stat in party_cluster_stats:
#         party = stat['member__party__party']
#         cluster = stat['bill__cluster']
#         rate = stat['rate']
#         avg = cluster_avg.get(cluster, 0)
#         diff = rate - avg
#         party_diffs['party'].append({
#             'cluster': cluster,
#             'diff': round(diff, 2),
#             'rate': round(rate, 1),
#             'avg': round(avg, 1)
#         })
    
#     # 상위 5개 필터링
#     top_diffs = {
#         party: sorted(diffs, key=lambda x: abs(x['diff']), reverse=True)[:5]
#         for party, diffs in party_diffs.items()
#     }

#     return top_diffs

# def get_party_relative_diff_data(congress_num):
#     age = Age.objects.get(number=congress_num)
#     votes = Vote.objects.filter(age=age).select_related('member__party', 'bill')

#     vote_stats = (
#         votes.values(
#             cluster=F('bill__cluster'),
#             party=F('member__party__party'),
#             vote_result=F('result')
#         )
#         .annotate(count=Count('id'))
#     )

#     total_votes = (
#         votes.values(cluster=F('bill__cluster'), party=F('member__party__party'))
#         .annotate(total=Count('id'))
#     )
#     total_lookup = {(x['cluster'], x['party']): x['total'] for x in total_votes}

#     # 클러스터-정당별 찬반 수 저장
#     result = defaultdict(lambda: defaultdict(lambda: {'찬성': 0, '반대': 0}))
#     for row in vote_stats:
#         cluster = row['cluster']
#         party = row['party']
#         vote_type = row['vote_result']
#         count = row['count']
#         if vote_type in ['찬성', '반대']:
#             result[cluster][party][vote_type] += count
    
#     all_parties = set()
#     for cluster_data in result.values():
#         all_parties.update(cluster_data.keys())

#     # 시각화용 데이터 저장
#     visual_data = {}
#     for cluster, party_data in result.items():
#         cluster_parties = {}
#         support_rates = []
#         oppose_rates = []

#         for party, counts in party_data.items():
#             total = total_lookup.get((cluster, party), 1)
#             support = counts['찬성'] / total
#             oppose = counts['반대'] / total

#             cluster_parties[party] = {
#                 'support': round(support * 100, 1),
#                 'oppose': round(oppose * 100, 1)
#             }
#             support_rates.append(support)
#             oppose_rates.append(oppose)
        
#         visual_data[cluster] = {
#             'avg_support': round(sum(support_rates) / len(support_rates) * 100, 1),
#             'avg_oppose': round(sum(oppose_rates) / len(oppose_rates) * 100, 1),
#             'parties': cluster_parties
#         }

#     # 정당별 편차 큰 클러스터 찾기
#     party_relative_diff = {}
#     for party in all_parties:
#         max_support_diff = -1
#         max_oppose_diff = -1
#         max_support_cluster = None
#         max_oppose_cluster = None

#         for cluster, party_data in result.items():
#             if party not in party_data: # 예외 처리
#                 continue

#             total = total_lookup.get((cluster, party), 1)
#             this_support = party_data[party]['찬성'] / total
#             this_oppose = party_data[party]['반대'] / total

#             # 해당 클러스터에서, 타 정당들의 평균
#             other_supports = []
#             other_opposes = []
#             for other_party, counts in party_data.items():
#                 if other_party == party: # 현 정당일 경우 패스
#                     continue
#                 other_total = total_lookup.get((cluster, other_party), 1)
#                 other_supports.append(counts['찬성'] / other_total)
#                 other_opposes.append(counts['반대'] / other_total)
#             if not other_supports or not other_opposes:
#                 continue

#             # 평균 찬성/반대율 구하기
#             avg_support = sum(other_supports) / len(other_supports)
#             avg_oppose = sum(other_opposes) / len(other_opposes)
            
#             # 편차
#             support_diff = abs(this_support - avg_support)
#             oppose_diff = abs(this_oppose - avg_oppose)

#             # 편차 큰 클러스터 구하기
#             if support_diff > max_support_diff:
#                 max_support_diff = support_diff
#                 max_support_cluster = cluster
#             if oppose_diff > max_oppose_diff:
#                 max_oppose_diff = oppose_diff
#                 max_oppose_cluster = cluster
#         visual_entry = {}
#         for label, cluster_id in {
#             'relative_support_cluster': max_support_cluster,
#             'relative_oppose_cluster': max_oppose_cluster,
#         }.items():
#             if cluster_id is not None:
#                 cluster_visual = visual_data.get(cluster_id, {})
#                 parties_data = cluster_visual.get('parties', {})
#                 this_party_data = parties_data.get(party, {'support': 0, 'oppose': 0})
#                 visual_entry[cluster_id] = {
#                 '찬성': {
#                     'party_percentage': this_party_data['support'],
#                     'average_percentage': cluster_visual.get('avg_support', 0),
#                 },
#                 '반대': {
#                     'party_percentage': this_party_data['oppose'],
#                     'average_percentage': cluster_visual.get('avg_oppose', 0),
#                 }
#             }
        
#         party_relative_diff[party] = {
#             'relative_support_cluster': max_support_cluster,
#             'relative_oppose_cluster': max_oppose_cluster,
#             'visual_data': visual_entry
#         }

#     # 구조 단순화
#     simplified_result = {}
#     for party, data in party_relative_diff.items():
#         simplified_result[party] = {}

#         for label in ['relative_support_cluster', 'relative_oppose_cluster']:
#             cluster_id = data[label]
#             if cluster_id is None:
#                 continue

#             cluster_data = data['visual_data'].get(cluster_id, {})
#             simplified_result[party][label.replace('_cluster', '')] = {
#                 'cluster': cluster_id,
#                 '찬성': cluster_data.get('찬성', {
#                     'party_percentage': 0,
#                     'average_percentage': 0
#                 }),
#                 '반대': cluster_data.get('반대', {
#                     'party_percentage': 0,
#                     'average_percentage': 0
#                 }),
#             }
#     flattened_result = []
#     for party, data in simplified_result.items():
#         for label_key in ['support', 'oppose']:
#             cluster_info = data.get(label_key)
#             if not cluster_info:
#                 continue

#             flattened_result.append({
#                 'party': party,
#                 'label': label_key,  # 'support' or 'oppose'
#                 'cluster': cluster_info['cluster'],
#                 '찬성': cluster_info['찬성'],
#                 '반대': cluster_info['반대'],
#             })
#     return flattened_result

def dashboard(request, congress_num):
    # 대수 필터링
    if congress_num not in [20, 21, 22]: # 유효하지 않은 링크 처리
        raise Http404("Invalid congress num")

    data = get_partyStats_data(congress_num)
    cluster_vote_data = get_partyClusterStats_data(congress_num, top_n_clusters=10)
    party_concentration_data = get_partyConcentration_data(congress_num)

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

    # 성별 차트
    # divergence_ranking = get_gender_vote_data()

    # 정당 클러스트 하이라이트 차트
    # top_diffs = get_party_cluster_highlight()

    # 정당별 특이 클러스트 목록
    # party_relative_diff = get_party_relative_diff_data(congress_num)
    # print(party_relative_diff)

    context = {
        'congress_num': congress_num,
        'party_names': data['party_names'],
        'party_colors': data['party_colors'],
        'series': data['series'], 
        'categories': data['categories'], 

        'total_votes': data['total_votes'],
        'total_bills': data['total_bills'],
        'total_parties': data['total_parties'],
        'gender_ratio': data['gender_ratio'],

        'cluster_vote_data': json.dumps(cluster_vote_data),
        'cluster_keywords': cluster_vote_data['cluster_keywords'],
        'cluster_nums': list(cluster_vote_data['cluster_keywords'].keys()),

        # 'ranking_data': divergence_ranking,

        # 'top_diffs': json.dumps(top_diffs),

        # 'party_relative_diff': party_relative_diff,
        # 'labels': ['relative_support', 'relative_oppose'],
        # 'vote_types': ['찬성', '반대'],

        # 정당 집중도 관련 데이터 추가
        'party_concentration_names': party_concentration_data.get('party_names', []),
        'party_concentration_member_counts': party_concentration_data.get('member_counts', []),
        'party_concentration_vote_supports': party_concentration_data.get('vote_supports', []),
        'party_concentration_top2_seat_shares': party_concentration_data.get('top2_seat_shares', []),
        'party_concentration_top2_ratio': party_concentration_data.get('top2_ratio'),
        'party_concentration_hhi': party_concentration_data.get('hhi'),
        'party_concentration_age': party_concentration_data.get('age'),
    }

    return render(request, 'dashboard.html', context)