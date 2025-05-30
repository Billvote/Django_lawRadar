from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from collections import Counter
from geovote.models import Vote, Member, Party
from billview.models import Bill

def get_data_for_congress(congress_num):
    votes = Vote.objects.filter(age=congress_num).select_related('member__party')

    # 정당별 표결 통계
    parties = Party.objects.all()
    party_stats = []
    for party in parties:
        party_votes = votes.filter(member__party=party)
        party_stats.append({
            'party': party.party,
            'agree': party_votes.filter(result='찬성').count(),
            'oppose': party_votes.filter(result='반대').count(),
            'abstain': party_votes.filter(result='기권').count(),
        })
   
    total_bills = Bill.objects.filter(age=congress_num).count() # 대수별 총 의안
    total_parties = Member.objects.filter(age=congress_num).values('party').distinct().count()
    gender_counts = Member.objects.filter(age=congress_num).values('gender').annotate(count=Count('id'))

    # 성비 정리
    male_count = 0
    female_count = 0
    
    for g in gender_counts:
        if g['gender'] == '남성':
            male_count = g['count']
        elif g['gender'] == '여성':
            female_count = g['count']

    total = male_count + female_count
    female_percent = round((female_count / total) * 100, 1) if total > 0 else 0

    return {
        'party_stats': party_stats,
        'total_votes': votes.count(),
        # 'total_members': total_members,
        'total_bills': total_bills,
        'total_parties': total_parties,
        'gender_ratio': {
            'male': male_count,
            'female': female_count,
            'female_percent': female_percent,
        }
    }

def dashboard(request, congress_num):
    if congress_num not in [20, 21, 22]: # 유효하지 않은 링크 처리
        raise Http404("Invalid congress num")

    data = get_data_for_congress(congress_num)
    context = {
        'congress_num': congress_num,
        'party_stats': data['party_stats'],
        'total_votes': data['total_votes'],
        # 'total_members': data['total_members'],
        'total_bills': data['total_bills'],
        'total_parties': data['total_parties'],
        'gender_ratio': data['gender_ratio'],
    }

    return render(request, 'dashboard.html', context)