import os
import django
import json
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # 프로젝트 루트 경로 추가
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lawRadar.settings') # Django 환경 설정
django.setup()

from geovote.models import Age, Party, Member, Vote
from billview.models import Bill
from main.models import AgeStats, PartyStats, PartyClusterStats, ClusterKeyword, PartyConcentration, VoteSummary
from django.db.models import Count, F, Avg, Q
from collections import defaultdict

def import_agesStats(congress_num):
    try:
        age = Age.objects.get(number=congress_num)
    except Age.DoesNotExist:
        print(f"{congress_num}대에 해당하는 Age 객체가 없습니다.")
        return

    total_bills = Bill.objects.filter(age=age).count()
    total_parties = Member.objects.filter(age=age).values('party').distinct().count()
    
    gender_counts = Member.objects.filter(age=age).values('gender').annotate(count=Count('id'))
    male_count = 0
    female_count = 0
    for g in gender_counts:
        if g['gender'] == '남':
            male_count = g['count']
        elif g['gender'] == '여':
            female_count = g['count']

    total = male_count + female_count
    female_percent = round((female_count / total) * 100, 1) if total > 0 else 0

    # HHI 계산
    pcs = PartyConcentration.objects.filter(age=age)
    total_members = sum(pc.member_count for pc in pcs)
    if total_members > 0:
        seat_shares = [pc.member_count / total_members * 100 for pc in pcs]

        hhi = sum((share / 100) ** 2 for share in seat_shares)
        
        enp_denominator = sum((share / 100) ** 2 for share in seat_shares)
        enp = 1 / enp_denominator if enp_denominator > 0 else 0
    
    else:
        hhi = 0
        enp = 0

    age_stats, created = AgeStats.objects.update_or_create(
        age=age,
        defaults={
            'total_bills': total_bills,
            'total_parties': total_parties,
            'male_count': male_count,
            'female_count': female_count,
            'female_percent': female_percent,
            'hhi': round(hhi, 4),
            'enp': round(enp, 4),
        }
    )
    print(f"AgeStats 저장됨: {age_stats}")

# 정당별 투표 통계
def import_partyStats(congress_num):
    try:
        age = Age.objects.get(number=congress_num)
    except Age.DoesNotExist:
        print(f"{congress_num}대에 해당하는 Age 객체가 없습니다.")
        return

    votes = Vote.objects.filter(age=age).select_related('member__party')

    # 정당별 멤버 수 집계
    top_parties = (
        Member.objects.filter(age=age)
        .values('party')
        .annotate(member_count=Count('id'))
        .order_by('-member_count')
    )
    top_party_ids = [p['party'] for p in top_parties]
    parties = Party.objects.filter(id__in=top_party_ids)

    # party_id를 key로 멤버 수를 빠르게 조회하기 위한 딕셔너리
    member_count_map = {p['party']: p['member_count'] for p in top_parties}

    # result_types = ['찬성', '반대', '기권', '불참']

    for party in parties:
        party_votes = votes.filter(member__party=party)
        total_votes = party_votes.count()

        support_count = party_votes.filter(result='찬성').count()
        oppose_count = party_votes.filter(result='반대').count()
        abstain_count = party_votes.filter(result='기권').count()
        absent_count = party_votes.filter(result='불참').count()

        member_count = member_count_map.get(party.id, 0)

        # 비율 계산
        support_ratio = (support_count / total_votes * 100) if total_votes else 0
        oppose_ratio = (oppose_count / total_votes * 100) if total_votes else 0
        abstain_ratio = (abstain_count / total_votes * 100) if total_votes else 0
        absent_ratio = (absent_count / total_votes * 100) if total_votes else 0

        pvs, created = PartyStats.objects.update_or_create(
            age=age,
            party=party,
            defaults={
                'member_count': member_count,
                'support_ratio': support_ratio,
                'oppose_ratio': oppose_ratio,
                'abstain_ratio': abstain_ratio,
                'absent_ratio': absent_ratio,
                'total_votes': total_votes,
            }
        )
        print(f"PartyStats 저장됨: {pvs}")

# 정당/클러스터별 표결 통계
def import_partyClusterStats(congress_num, top_n_clusters=20):
    try:
        age = Age.objects.get(number=congress_num)
    except Age.DoesNotExist:
        print(f"{congress_num}대에 해당하는 Age 객체가 없습니다.")
        return

    votes = Vote.objects.filter(age=age).select_related('member__party', 'bill')

    # 해당 대수의 모든 정당 조회
    party_ids_in_age = Member.objects.filter(age=age).values_list('party', flat=True).distinct()
    parties = Party.objects.filter(id__in=party_ids_in_age)

    # 투표 결과 집계
    vote_summary = (
        votes
        .values(
            cluster=F('bill__cluster'),
            cluster_keyword=F('bill__cluster_keyword'),
            party_name=F('member__party__party'),
            vote_result=F('result')
        )
        .annotate(count=Count('id'))
    )

    # 총 투표 수 계산 (클러스터-정당별)
    total_votes_qs = (
        votes
        .values(cluster=F('bill__cluster'), party_name=F('member__party__party'))
        .annotate(total_count=Count('id'))
    )
    total_dict = {(tv['cluster'], tv['party_name']): tv['total_count'] for tv in total_votes_qs}

    # 결과 정리
    result_types = ['찬성', '반대', '기권', '불참']
    cluster_party_result = {}

    for row in vote_summary:
        cluster = row['cluster']
        keyword = row['cluster_keyword']
        party_name = row['party_name']
        result = row['vote_result']
        count = row['count']

        if cluster not in cluster_party_result:
            cluster_party_result[cluster] = {}
        if party_name not in cluster_party_result[cluster]:
            cluster_party_result[cluster][party_name] = {r: 0 for r in result_types}
        cluster_party_result[cluster][party_name][result] += count

        # ClusterKeyword도 저장
        ClusterKeyword.objects.update_or_create(
            age=age,
            cluster_num=cluster,
            defaults={'keyword_json': json.dumps(keyword) if isinstance(keyword, (list, dict)) else str(keyword)}
        )

    # 모든 클러스터에 대해 저장
    for cluster_num, party_data in cluster_party_result.items():
        for party in parties:
            party_name = party.party
            result_counts = party_data.get(party_name, {r: 0 for r in result_types})
            total = total_dict.get((cluster_num, party_name), 0)

            if total > 0:
                support_ratio = (result_counts['찬성'] / total) * 100
                oppose_ratio = (result_counts['반대'] / total) * 100
                abstain_ratio = (result_counts['기권'] / total) * 100
                absent_ratio = (result_counts['불참'] / total) * 100
            else:
                support_ratio = oppose_ratio = abstain_ratio = absent_ratio = 0

            pcs, created = PartyClusterStats.objects.update_or_create(
                age=age,
                cluster_num=cluster_num,
                party=party,
                defaults={
                    'cluster_keyword': json.dumps(party_data.get(party_name, {})),
                    'support_ratio': support_ratio,
                    'oppose_ratio': oppose_ratio,
                    'abstain_ratio': abstain_ratio,
                    'absent_ratio': absent_ratio,
                    'total_votes': total,
                    }
                    )
            print(f"PartyClusterStats 저장됨: {pcs}")

def import_partyConcentration(congress_num):
    try:
        age = Age.objects.get(number=congress_num)
    except Age.DoesNotExist:
        print(f"{congress_num}대에 해당하는 Age 객체가 없습니다.")
        return

    all_parties = (
    Member.objects.filter(age=age)
    .values('party')
    .annotate(member_count=Count('id'))
    .order_by('-member_count')  # 전체 정당 다 가져옴
    )
    
    total_members = sum([p['member_count'] for p in all_parties])  # 전체 의원 수 계산

    # 찬성 비율 구하기 (전체 정당에 대해)
    party_ids = [p['party'] for p in all_parties]
    vote_supports = (
        PartyClusterStats.objects.filter(age=age, party__in=party_ids)
        .values('party')
        .annotate(avg_support=Avg('support_ratio'))
    )
    vote_support_dict = {v['party']: v['avg_support'] for v in vote_supports}

    for rank, party_data in enumerate(all_parties, start=1):
        party_obj = Party.objects.get(id=party_data['party'])
        seat_share = (party_data['member_count'] / total_members * 100) if total_members > 0 else 0
        
        PartyConcentration.objects.update_or_create(
            age=age,
            party=party_obj,
            rank=rank,
            defaults={
                'rank': rank,
                'member_count': party_data['member_count'],
                'vote_support_ratio': vote_support_dict.get(party_obj.id, 0),
                'seat_share': seat_share,
            }
        )
    print(f"PartyConcentration 저장 완료: {congress_num}대")

# 의원 표결 데이터 

def import_votesummary(congress_num=None, member_name=None):
    """
    - member_name이 주어지면 해당 의원만 처리
    - congress_num이 주어지면 해당 대수의 모든 의원 처리
    """
    if member_name:
        member_names = [member_name]
    elif congress_num:
        member_names = Member.objects.filter(age__number=congress_num).values_list('name', flat=True).distinct()
    else:
        print("member_name 또는 congress_num 둘 중 하나는 필요합니다.")
        return

    for name in member_names:
        try:
            votes = Vote.objects.filter(member__name=name)\
                .values('bill__cluster', 'result')\
                .annotate(count=Count('id'))

            if not votes:
                print(f"{name} 의원의 표결 데이터가 없습니다.")
                continue

            clusters = {v['bill__cluster'] for v in votes if v['bill__cluster']}
            if not clusters:
                continue

            # 🔸 클러스터 키워드 및 법안 수 한번에 조회
            bill_info = (
                Bill.objects
                .filter(cluster__in=clusters)
                .values('cluster')
                .annotate(
                    keyword=Count('cluster_keyword'),  # 그냥 1개 대표값으로 봄
                    bill_count=Count('id')
                )
            )
            cluster_keywords = {b['cluster']: b.get('keyword', '알 수 없음') for b in bill_info}
            cluster_bill_counts = {b['cluster']: b.get('bill_count', 0) for b in bill_info}

            # 🔸 표결 결과 요약
            cluster_summary = defaultdict(lambda: {'찬성': 0, '반대': 0, '기권': 0, '불참': 0})
            for vote in votes:
                cluster = vote['bill__cluster']
                result = vote['result']
                if cluster is None:
                    continue
                if result not in cluster_summary[cluster]:
                    result = '기권'
                cluster_summary[cluster][result] += vote['count']

            # 🔸 기존 데이터 삭제
            VoteSummary.objects.filter(member_name=name).delete()

            # 🔸 bulk insert
            summaries = []
            for cluster, summary in cluster_summary.items():
                summaries.append(VoteSummary(
                    member_name=name,
                    cluster=cluster,
                    cluster_keyword=cluster_keywords.get(cluster, '알 수 없음'),
                    bill_count=cluster_bill_counts.get(cluster, 0),
                    찬성=summary['찬성'],
                    반대=summary['반대'],
                    기권=summary['기권'],
                    불참=summary['불참'],
                ))
            VoteSummary.objects.bulk_create(summaries)

            print(f"{name} 의원 VoteSummary 저장 완료 (총 {len(summaries)}개).")

        except Exception as e:
            print(f"{name} 처리 중 오류 발생: {e}")

# 데이터 import

def run_all(congress_num):
    print(f"{congress_num}대 데이터 임포트 시작")
    import_partyStats(congress_num)
    import_partyClusterStats(congress_num)
    import_partyConcentration(congress_num)
    import_agesStats(congress_num)
    import_votesummary(congress_num)


    print(f"{congress_num}대 데이터 임포트 완료")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        congress_num = int(sys.argv[1])
        run_all(congress_num)
    else:
        print("사용법: python import_db.py [국회대수]")
