from django.shortcuts import render
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
# from .models import District
import json

# # geojson api
# def district_geojson(request):
#     features = []
#     for district in District.objects.all():
#         # 각 지역구에 속한 가장 최근 대수의 의원 가져오기 (예: 22대만 필터링)
#         member = district.member_set.filter(age=22).first()  # 원하는 대수로 필터링 가능

#         feature = {
#             "type": "Feature",
#             "geometry": district.boundary,
#             "properties": {
#                 "SIDO_SGG": district.SIDO_SGG,
#                 "SGG": district.SGG,
#                 "SIDO": district.SIDO,
#                 "member_name": member.name if member else None,
#                 "party": str(member.party.party) if member and member.party else None,
#                 "gender": member.gender if member else None,
#             },
#         }
#         features.append(feature)

#     return JsonResponse(
#         {"type": "FeatureCollection", "features": features},
#         json_dumps_params={'ensure_ascii': False}) # 한글 깨짐 문제 해결

def geovote_main(request):
    return render(request, 'geovote_main.html')

def map_view(request):
    return render(request, 'map_22대.html')

# # 테스트용
# def map22(request):
#     return render(request, 'map_22.html')

#-------------------------------tree map -------------------------------

from django.shortcuts import render
from django.http import JsonResponse
from .models import Age, Member, District
from collections import defaultdict

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
                    label = f"{district.SGG} ({member.name} - {member.party.party})"
                    color = member.party.color
                else:
                    label = f"{district.SGG} (의원 없음)"
                    color = "#cccccc"
                sigungu_node["children"].append({
                    "id": district.id,
                    "member_name": member.name if member else None,
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
from django.db.models import Count
from .models import Vote

def member_vote_summary_api(request):
    member_name = request.GET.get('member_name')
    if not member_name:
        return JsonResponse({'error': 'member_name parameter is required'}, status=400)

    try:
        votes = Vote.objects.filter(member__name=member_name)\
            .values('bill__cluster', 'bill__name', 'result')\
            .annotate(count=Count('id'))\
            .order_by('bill__cluster')
    except Exception as e:
        print(f"🔥 Error fetching votes for member: {member_name}")
        print(f"🔥 Exception: {e}")
        return JsonResponse({'error': 'Failed to fetch votes', 'details': str(e)}, status=500)

    cluster_summary = {}
    for vote in votes:
        cluster = vote['bill__cluster']
        if cluster not in cluster_summary:
            cluster_summary[cluster] = {'cluster': cluster, 'bills': {}}
        bill_name = vote['bill__name']
        if bill_name not in cluster_summary[cluster]['bills']:
            cluster_summary[cluster]['bills'][bill_name] = {'찬성': 0, '반대': 0, '기타': 0}
        result = vote['result']
        if result == '찬성':
            cluster_summary[cluster]['bills'][bill_name]['찬성'] += vote['count']
        elif result == '반대':
            cluster_summary[cluster]['bills'][bill_name]['반대'] += vote['count']
        else:
            cluster_summary[cluster]['bills'][bill_name]['기타'] += vote['count']

    data = []
    for cluster, info in cluster_summary.items():
        bills_list = []
        for bill_name, counts in info['bills'].items():
            bills_list.append({
                'bill_name': bill_name,
                '찬성': counts['찬성'],
                '반대': counts['반대'],
                '기타': counts['기타']
            })
        data.append({'cluster': cluster, 'bills': bills_list})

    return JsonResponse(data, safe=False)













