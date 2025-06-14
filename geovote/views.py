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

from django.http import JsonResponse
from .models import District, Member
from django.db.models import Prefetch
import logging

logger = logging.getLogger(__name__)

def region_tree_data(request):
    result = {"name": "대한민국", "children": []}

    # 1. 시도 목록
    sido_list = District.objects.values_list('SIDO', flat=True).distinct()

    # 2. 전체 의원 미리 가져오기 (district 포함)
    members = Member.objects.select_related('district')
    
    # 3. 지역구 ID별로 의원 목록 묶기
    from collections import defaultdict
    member_dict = defaultdict(list)
    for m in members:
        if m.district:
            member_dict[m.district.id].append(m)

    # 4. 시도 > 선거구 > 의원 구조 생성
    for sido_name in sido_list:
        districts = District.objects.filter(SIDO=sido_name)
        sido_children = []

        for district in districts:
            district_members = member_dict.get(district.id, [])
            if district_members:
                member_nodes = []
                for member in district_members:
                    try:
                        age_value = int(member.age)
                    except (ValueError, TypeError):
                        age_value = 0  # 혹은 None 처리 가능

                    member_nodes.append({
                        "name": f"{member.name} ({member.party_id})",
                        "value": age_value
                    })
            else:
                member_nodes = [{"name": "의원 없음", "value": 0}]

            district_node = {
                "name": district.SGG,
                "children": member_nodes
            }
            sido_children.append(district_node)

        result["children"].append({
            "name": sido_name,
            "children": sido_children
        })

    return JsonResponse(result)

def treemap_view(request):
    return render(request, 'treemap.html')


