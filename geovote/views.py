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

    # SIDO > SIGUNGU > District 계층 구조 생성
    tree = defaultdict(lambda: defaultdict(list))
    for district in districts:
        sido = district.SIDO or "기타"
        sigungu = district.SIGUNGU or "기타"
        # district.id가 중복되지 않도록 set 사용
        if district not in tree[sido][sigungu]:
            tree[sido][sigungu].append(district)


    result = {
        "name": "대한민국",
        "children": []
    }

    for sido_name, sigungu_map in tree.items():
        sido_node = {"name": sido_name, "children": []}
        for sigungu_name, district_list in sigungu_map.items():
            # SIGUNGU 아래에 district가 1개뿐이거나 SIGUNGU와 SGG가 같으면 SIGUNGU 계층 생략
            if len(district_list) == 1 and (sigungu_name == district_list[0].SGG or len(sigungu_map) == 1):
                district = district_list[0]
                member = member_dict.get(district.id)
                if member:
                    label = f"{district.SGG} ({member.name} - {member.party.party})"
                    color = member.party.color
                else:
                    label = f"{district.SGG} (의원 없음)"
                    color = "#cccccc"
                sido_node["children"].append({
                    "name": label,
                    "value": 1,
                    "color": color
                })
            else:
                sigungu_node = {"name": sigungu_name, "children": []}
                for district in district_list:
                    member = member_dict.get(district.id)
                    if member:
                        label = f"{district.SGG} ({member.name} - {member.party.party})"
                        color = member.party.color
                    else:
                        label = f"{district.SGG} (의원 없음)"
                        color = "#cccccc"
                    sigungu_node["children"].append({
                        "name": label,
                        "value": 1,
                        "color": color
                    })
                sido_node["children"].append(sigungu_node)
        result["children"].append(sido_node)

    return JsonResponse(result)









