from django.core.paginator import Paginator
from django.db.models import Count, Q, F, Max
from collections import defaultdict
from django.shortcuts import render
from geovote.models import Vote
from .models import Bill
from main.models import PartyStats
import json

def get_vote_heatmap_data():
    vote_qs = Vote.objects.select_related('member', 'bill').all()

    members = sorted(set(v.member.name for v in vote_qs))
    bills = sorted(set(v.bill.title for v in vote_qs))

    data = defaultdict(dict)  # member_name -> bill_title -> vote_result

    for vote in vote_qs:
        member = vote.member.name
        bill = vote.bill.title
        result = vote.vote_result
        data[member][bill] = result

    return {
        'heatmap_data': json.dumps(data, ensure_ascii=False),
        'members': json.dumps(members),
        'bills': json.dumps(bills),
    }


def detail_bill(request, id):
    bill = Bill.objects.get(id=id)
    # votes = Vote.objects.filter(bill=bill).select_related('member', 'member__party')
    votes = Vote.objects.select_related('member', 'member__party').filter(bill=bill)

    # 정당/정당 리스트
    parties = sorted(set(vote.member.party.party for vote in votes))
    members = sorted(set(vote.member.name for vote in votes))

    # 정당별로 members에 대응하는 결과 채우기
    # data[party][member] = vote_result (없으면 '불참')
    data = defaultdict(dict)
    for vote in votes:
        party = vote.member.party.party
        member = vote.member.name
        result = vote.result
        data[party][member] = result

    # y축(정당)별로 members 순서대로 결과 리스트 만들기
    heatmap_data = []
    for party in parties:
        row = []
        for member in members:
            row.append(data[party].get(member, '불참'))
        heatmap_data.append(row)

    results = ['찬성', '반대', '기권', '불참']
# ------
    # 의원-표결 매핑
    vote_map = {vote.member.name: vote.result for vote in votes}

    # member 순서대로 결과 리스트 생성
    results = [vote_map.get(member, '불참') for member in members]

    # 10행 30열 크기로 자르기 (필요하면 멤버 수에 맞게 조정)
    # row_length = 30
    # heatmap_data = []
    # for i in range(0, len(results), row_length):
    #     heatmap_data.append(results[i:i+row_length])

    # members = []
    # results = []


    # for vote in votes:
    #     member_name = f"{vote.member.name} ({vote.member.party})"  # 혹은 .party.party
    #     members.append(member_name)
    #     results.append(vote.result)

    if bill.label:
        revision_count = Bill.objects.filter(label=bill.label).count()
    else:
        revision_count = 1

    # 최근 표결 날짜
    last_vote_date = votes.aggregate(last_date=Max('date'))['last_date']

    # 1차원 results 리스트를 10 x 30 2차원 리스트로 변환
    heatmap_data = []
    row_length = 30
    for i in range(0, len(results), row_length):
        heatmap_data.append(results[i:i+row_length])

    context = {
        'bill': bill,
        # 'results': results,
        'last_vote_date': last_vote_date,
        'revision_count': revision_count,  # 개정 횟수
        'results': results,

        'heatmap_data': json.dumps(heatmap_data, ensure_ascii=False),
        'members': json.dumps(members, ensure_ascii=False),
        'parties': json.dumps(parties, ensure_ascii=False)
        # 'bill_title': json.dumps(bill.title, ensure_ascii=False),  # x축 하나
    }
    # heatmap = get_vote_heatmap_data()
    
    # bill_age = bill.age # Bill의 age 값을 가져옴

    # party_stats = Vote.objects.filter(
    #     bill=bill,
    #     member__age=bill_age
    # ).annotate(
    #     party_party=F('member__party__party')
    # ).values(
    #     'party_party'
    # ).annotate(
    #     agree=Count('id', filter=Q(result='찬성')),
    #     oppose=Count('id', filter=Q(result='반대')),
    #     abstain=Count('id', filter=Q(result='기권')),
    # )

    # context = {
    #     'bill': bill,
    #     'votes': votes,
    #     'party_stats': party_stats,

    #     'heatmap_data': json.dumps(heatmap['heatmap_data']),
    #     'heatmap_members': json.dumps(heatmap['members']),
    #     'heatmap_bills': json.dumps(heatmap['bills']),
    # }
    return render(request, 'detail.html', context)

def index_bill(request):
    bills = Bill.objects.all()
    paginator = Paginator(bills, 10)  # 페이지당 10개
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    current_page = page_obj.number # 현재 페이지 번호
    total_pages = paginator.num_pages # 총 페이지
    max_page_buttons = 10 # 한번에 보여줄 최대 수

    # 현재 페이지 번호가 속한 10페이지 그룹을 구함
    group = (current_page - 1) // max_page_buttons
    
    start_page = group * max_page_buttons + 1
    end_page = min(start_page + max_page_buttons - 1, total_pages)
    
    page_range = range(start_page, end_page + 1)

    context = {
        'page_obj': page_obj,
        'page_range': page_range
    }
    return render(request, 'index.html', context)
