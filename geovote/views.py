from django.shortcuts import render
from django.http import JsonResponse
from .models import Age, Member, District
from collections import defaultdict
from billview.models import Bill
from main.models import VoteSummary, PartyClusterStats
from django.views.decorators.http import require_GET

def treemap_view(request):
    ages = Age.objects.all().order_by('number')
    return render(request, 'treemap.html', {'ages': ages})


def region_tree_data(request):
    age_id = request.GET.get('age')
    if not age_id:
        return JsonResponse({"error": "age parameter is required"}, status=400)

    try:
        age_id = int(age_id)
        age_obj = Age.objects.get(id=age_id)
    except (ValueError, Age.DoesNotExist):
        return JsonResponse({"error": "Invalid age parameter"}, status=400)

    members = Member.objects.filter(age=age_obj).select_related('party', 'district')
    member_dict = {m.district_id: m for m in members if m.district_id}

    districts = District.objects.filter(id__in=member_dict.keys())

    tree = defaultdict(lambda: defaultdict(list))
    for district in districts:
        sido = district.SIDO or "기타"
        sigungu = district.SIGUNGU or "기타"
        tree[sido][sigungu].append(district)

    result = {
        "name": "대한민국",
        "type": "ROOT",
        "children": []
    }

    for sido_name, sigungu_map in tree.items():
        sido_node = {"name": sido_name, "type": "SIDO", "children": []}
        for sigungu_name, district_list in sigungu_map.items():
            sigungu_node = {"name": sigungu_name, "type": "SIGUNGU", "children": []}
            for district in district_list:
                member = member_dict.get(district.id)
                if member:
                    label = f"{district.SGG}\n({member.name} - {member.party.party})"
                    color = member.party.color
                else:
                    label = f"{district.SGG} (의원 없음)"
                    color = "#cccccc"
                sigungu_node["children"].append({
                    "id": district.id,
                    "member_name": member.name if member else None,
                    "image_url": member.image_url if member else None,
                    "name": label,
                    "type": "District",
                    "value": 1,
                    "color": color
                })
            sido_node["children"].append(sigungu_node)
        result["children"].append(sido_node)

    return JsonResponse(result)

#----------------------의원 - 의안 클러스터 - 표결 연결 ------------------
from django.http import JsonResponse

MIN_VOTE_COUNT = 3

def get_ratio(summary, vote_type):
    total = summary.찬성 + summary.반대 + summary.기권 + summary.불참
    return getattr(summary, vote_type) / total if total else 0

def get_confidence_level(vote_count):
    if vote_count >= 30:
        return "High"
    elif vote_count >= MIN_VOTE_COUNT:
        return "Medium"
    else:
        return "Low"

def member_vote_summary_api(request):
    member_name = request.GET.get('member_name')
    if not member_name:
        return JsonResponse({'error': 'member_name parameter is required'}, status=400)

    summaries = VoteSummary.objects.filter(member__name=member_name)
    if not summaries.exists():
        return JsonResponse({'error': 'No summary data available. Please generate it first.'}, status=404)

    max_clusters = {}

    for vote_type in ['찬성', '반대', '기권', '불참']:
        filtered = [
            s for s in summaries
            if (s.찬성 + s.반대 + s.기권 + s.불참) >= MIN_VOTE_COUNT
        ]

        if not filtered:
            continue

        top_summary = max(filtered, key=lambda s: get_ratio(s, vote_type))

        vote_count = top_summary.찬성 + top_summary.반대 + top_summary.기권 + top_summary.불참
        confidence = get_confidence_level(vote_count)

        counts = {
            '찬성': top_summary.찬성,
            '반대': top_summary.반대,
            '기권': top_summary.기권,
            '불참': top_summary.불참,
        }
        total_votes = sum(counts.values()) or 1
        ratios = {k: round(counts[k] / total_votes * 100, 2) for k in counts}

        bill = Bill.objects.filter(cluster=top_summary.cluster).first()
        cluster_keyword = bill.cluster_keyword if bill and bill.cluster_keyword else "알 수 없음"

        max_clusters[vote_type] = {
            'cluster_keyword': cluster_keyword,
            'cluster_id': top_summary.cluster,
            'counts': counts,
            'ratios': ratios,
            'bill_count': top_summary.bill_count if top_summary.bill_count > 0 else 1,
            'confidence': confidence,
        }

    total_vote_count = sum(
        sum(v['counts'].values()) for v in max_clusters.values() if 'counts' in v
    )
    max_clusters['total_vote_count'] = total_vote_count

    return JsonResponse(max_clusters)



#------------------정당과 의원의 표결 경향 분석--------------------------------
# import logging
# logger = logging.getLogger(__name__)
@require_GET
def member_alignment_api(request):
    member_name = request.GET.get("member_name")
    congress_num = request.GET.get("congress_num")

    if not member_name or not congress_num:
        return JsonResponse({'error': 'member_name and congress are required'}, status=400)
    
    try:
        age = Age.objects.get(id=congress_num)
    except Age.DoesNotExist:
        logger.error(f"Age ID {congress_num} not found")
        return JsonResponse({'error': 'Invalid congress_num'}, status=404)

    try:
        member = Member.objects.get(name=member_name, age=age)
    except Member.DoesNotExist:
        return JsonResponse({'error': 'Member not found'}, status=404)

    party = member.party
    summaries = VoteSummary.objects.filter(member=member)
    if not summaries.exists():
        return JsonResponse({'error': 'No vote summary found for member'}, status=404)

    aligned = 0
    total = 0

    for s in summaries:
        try:
            party_stat = PartyClusterStats.objects.get(
                age=age, cluster_num=s.cluster, party=party
            )
        except PartyClusterStats.DoesNotExist:
            continue

        party_stance = max([
            ('찬성', party_stat.support_ratio),
            ('반대', party_stat.oppose_ratio),
            ('기권', party_stat.abstain_ratio)
        ], key=lambda x: x[1])[0]

        member_stance = max([
            ('찬성', s.찬성),
            ('반대', s.반대),
            ('기권', s.기권)
        ], key=lambda x: x[1])[0]

        if party_stance == member_stance:
            aligned += 1
        total += 1
    
    alignment_rate = round(aligned / total * 100, 2) if total else 0

    return JsonResponse({
        'member_name': member.name,
        'party': party.party,
        'alignment_count': aligned,
        'total_clusters': total,
        'alignment_rate': alignment_rate,
        'deviation_rate': round(100 - alignment_rate, 2),
    })




















