from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe
from django.db.models import Count, Min, Q, F
from collections import Counter
from geovote.models import Vote, Member, Party, Age
from billview.models import Bill
import json

def get_data_for_congress(congress_num):
    try:
        ages = Age.objects.get(number=congress_num)
    except Age.DoesNotExist:
        return {
            'error': f'{congress_num}대에 해당하는 Age 객체가 없습니다'
            }

    votes = Vote.objects.filter(age__number=congress_num).select_related('member__party')

    # 해당 대수에 투표한 정당만 가져오기
    party_ids = votes.values_list('member__party', flat=True).distinct()
    parties = Party.objects.filter(id__in=party_ids)

    # 모든 대수 공통: 멤버 수 기준 상위 8개 정당만 필터링
    top_parties = (
        Member.objects
        .filter(age=ages)
        .values('party', 'party__party', 'party__color')
        .annotate(member_count=Count('id'))
        .order_by('-member_count')[:8]
    )

    top_party_ids = [p['party'] for p in top_parties]
    parties = Party.objects.filter(id__in=top_party_ids)

    # 정당별 찬반기권불참 비율 계산
    result_types = ['찬성', '반대', '기권', '불참']
    series = []
    result_data = {r: [] for r in result_types}
    party_names = []
    party_colors = []

    for party in parties:
        party_votes = votes.filter(member__party=party)
        total = party_votes.count()

        proportions = {
        r: (party_votes.filter(result=r).count() / total * 100 if total else 0)
        for r in result_types
    }

        series.append({
            'name': party.party,
            'data': [round(proportions[r], 1) for r in result_types]
        })

        party_names.append(party.party)
        party_colors.append(party.color)

    # 카테고리는 표결 결과 (y축)
    categories = result_types


    #     for r in result_types:
    #         count = party_votes.filter(result=r).count()
    #         percent = (count / total * 100) if total > 0 else 0
    #         result_data[r].append(round(percent, 1))

    # series = [{'name': r, 'data': result_data[r]} for r in result_types]


    total_bills = Bill.objects.filter(age=ages).count() # 대수별 총 의안
    total_parties = Member.objects.filter(age=ages).values('party').distinct().count()
    gender_counts = Member.objects.filter(age=ages).values('gender').annotate(count=Count('id'))

    # 성비
    male_count = 0
    female_count = 0
    
    for g in gender_counts:
        if g['gender'] == '남':
            male_count = g['count']
        elif g['gender'] == '여':
            female_count = g['count']

    total = male_count + female_count
    female_percent = round((female_count / total) * 100, 1) if total > 0 else 0

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

def get_cluster_vote_summary_by_party(congress_num, top_n_clusters=20):
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

    # 클러스터별, 정당별 투표 결과 집계
    vote_summary = (
        votes
        .values(cluster=F('bill__cluster'), party_name=F('member__party__party'), party_color=F('member__party__color'), vote_result=F('result'))
        .annotate(count=Count('id'))
    )

    total_votes = (
        votes
        .values(cluster=F('bill__cluster'), party_name=F('member__party__party'))
        .annotate(total_count=Count('id'))
    )

    total_dict = {(tv['cluster'], tv['party_name']): tv['total_count'] for tv in total_votes}
    result_types = ['찬성', '반대', '기권', '불참']
    cluster_party_result = {}

    for v in vote_summary:
        key = (v['cluster'], v['party_name'])
        total = total_dict.get(key, 1)  # 0 나누기 방지
        ratio = v['count'] / total * 100
        cluster = v['cluster']
        party = v['party_name']
        result = v['vote_result']

        cluster_party_result.setdefault(cluster, {}).setdefault(party, {'찬성': 0, '반대': 0, '기권': 0, '불참': 0})
        cluster_party_result[cluster][party][result] = round(ratio, 1)

    # 상위 N개 클러스터 필터링
    cluster_vote_counts = (
        votes.values('bill__cluster')
        .annotate(vote_count=Count('id'))
        .order_by('-vote_count')
    )
    top_clusters = [c['bill__cluster'] for c in cluster_vote_counts[:top_n_clusters]]
    filtered_result = {c: cluster_party_result[c] for c in top_clusters if c in cluster_party_result}

    # 모든 클러스터에 대해 상위 정당의 데이터 보장
    for cluster in filtered_result:
        for party in party_names:
            if party not in filtered_result[cluster]:
                filtered_result[cluster][party] = {'찬성': 0, '반대': 0, '기권': 0, '불참': 0}

    return {
        'cluster_data': filtered_result,
        'party_names': party_names,
        'party_colors': party_colors,
        'result_types': result_types}

def dashboard(request, congress_num):
    if congress_num not in [20, 21, 22]: # 유효하지 않은 링크 처리
        raise Http404("Invalid congress num")

    data = get_data_for_congress(congress_num)
    cluster_vote_data = get_cluster_vote_summary_by_party(congress_num, top_n_clusters=10)

    # 1) 해당 회기(age)의 모든 bill 중에서 클러스터별 cluster_keyword 대표값 가져오기
    # (동일 클러스터 번호에 cluster_keyword가 여러 개일 경우, 가장 낮은 id(bill) 의 키워드 선택)
    bills = Bill.objects.filter(age__number=congress_num)

    # keyword_str = min_bill.cluster_keyword

    cluster_keywords_qs = (
        bills
        .values('cluster')
        .annotate(min_id=Min('id'))
        .order_by('cluster')
    )

    cluster_keywords = {}

    # cluster -> 대표 cluster_keyword mapping 만들기
    cluster_keywords = {}
    for entry in cluster_keywords_qs:
        cluster_num = entry['cluster']
        min_bill = bills.filter(cluster=cluster_num, id=entry['min_id']).first()
        
        if min_bill:
            keyword_str = min_bill.cluster_keyword
            if isinstance(keyword_str, str):
                try:
                    keyword_list = json.loads(keyword_str)
                    keyword_display = ', '.join(keyword_list)
                except Exception:
                    keyword_display = str(keyword_str)
            else:
                keyword_display = str(keyword_str)
            cluster_keywords[cluster_num] = keyword_display
        else:
            cluster_keywords[cluster_num] = str(cluster_num)

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
        'cluster_keywords': cluster_keywords,
    }

    return render(request, 'dashboard.html', context)