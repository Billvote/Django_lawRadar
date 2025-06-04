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

def treemap_view(request):
    ages = Age.objects.all().order_by('number')  # 대수 목록 (number 순)
    return render(request, 'treemap.html', {'ages': ages})

def region_tree_data(request):
    age_id = request.GET.get('age')
    if not age_id:
        return JsonResponse({"error": "age parameter is required"}, status=400)

    try:
        age_id = int(age_id)
    except ValueError:
        return JsonResponse({"error": "age parameter must be an integer"}, status=400)

    try:
        age_obj = Age.objects.get(id=age_id)
    except Age.DoesNotExist:
        return JsonResponse({"error": "Invalid age parameter"}, status=400)

    members = Member.objects.filter(age=age_obj).select_related('party', 'district')
    # print 전체 멤버 수 및 district 없는 멤버 확인
    print(f"Members count for age {age_obj.number}: {members.count()}")
    no_district_members = [m for m in members if m.district is None]
    print(f"Members without district: {len(no_district_members)}")

    member_dict = {m.district_id: m for m in members if m.district_id is not None}
    member_district_ids = list(member_dict.keys())
    print(f"District IDs linked to members: {member_district_ids}")

    if not member_district_ids:
        return JsonResponse({"error": "No districts linked to members for this age"}, status=404)

    districts_for_age = District.objects.filter(id__in=member_district_ids)
    sido_list = districts_for_age.values_list('SIDO', flat=True).distinct()
    print(f"SIDO list: {list(sido_list)}")

    result = {"name": "대한민국", "children": []}

    for sido in sido_list:
        if not sido:
            continue
        sido_node = {"name": sido, "children": []}

        sido_sgg_qs = districts_for_age.filter(SIDO=sido).values_list('SIDO_SGG', flat=True)
        sido_sgg_set = set(s.strip() for s in sido_sgg_qs if s and s.strip())
        print(f"SIDO_SGG set for {sido}: {sido_sgg_set}")

        for sido_sgg in sido_sgg_set:
            if not sido_sgg:
                continue
            district_for_name = districts_for_age.filter(SIDO_SGG=sido_sgg).first()
            sgg_name = district_for_name.SGG if district_for_name else sido_sgg
            sido_sgg_node = {"name": sgg_name, "children": []}
            districts = districts_for_age.filter(SIDO=sido, SIDO_SGG=sido_sgg)

            for district in districts:
                member = member_dict.get(district.id)
                if member:
                    label = f"{district.SGG} ({member.name} - {member.party.party})"
                    color = member.party.color
                else:
                    label = f"{district.SGG} (의원 없음)"
                    color = "#cccccc"
                sido_sgg_node["children"].append({
                    "name": label,
                    "value": 1,
                    "color": color
                })
            sido_node["children"].append(sido_sgg_node)
        result["children"].append(sido_node)

    return JsonResponse(result)





