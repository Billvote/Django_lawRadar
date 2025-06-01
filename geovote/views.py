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

from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


from django.db.models import Prefetch

def region_tree_data(request):
    result = {"name": "대한민국", "children": []}
    sido_list = District.objects.values_list('SIDO', flat=True).distinct()

    # 모든 Region에 대한 Member 미리 가져오기
    members = Member.objects.select_related('district', 'party')
    # member_dict = {m.district_id: m for m in members_by_region}

    # district_id 기준으로 그룹핑
    member_dict = {}
    for m in members:
        if m.district:
            member_dict[m.district.id] = m

    for sido_name in sido_list:
        # 해당 SIDO에 속한 시군구 District만 필터링
        sgg_districts = District.objects.filter(SIDO=sido_name)
        sido_children = []

        for district in sgg_districts:
            member = member_dict.get(district.id)
            if member:
                member_info = f"{member.name} ({member.party.party})"
            else:
                member_info = "의원 없음"

            sgg_node = {
                "name": district.SGG,
                "children": [
                    {
                        "name": member_info,
                        "value": 1
                    }
                ]
            }
            sido_children.append(sgg_node)

        result["children"].append({
            "name": sido_name,
            "children": sido_children
        })

    return JsonResponse(result)

def treemap_view(request):
    return render(request, 'treemap.html')



