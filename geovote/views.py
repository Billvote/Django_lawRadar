from django.shortcuts import render
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from .models import District
import json

# geojson api
def district_geojson(request):
    features = []
    for district in District.objects.all():
        # 각 지역구에 속한 가장 최근 대수의 의원 가져오기 (예: 22대만 필터링)
        member = district.member_set.filter(age=22).first()  # 원하는 대수로 필터링 가능

        feature = {
            "type": "Feature",
            "geometry": district.boundary,
            "properties": {
                "SIDO_SGG": district.SIDO_SGG,
                "SGG": district.SGG,
                "SIDO": district.SIDO,
                "member_name": member.name if member else None,
                "party": str(member.party.party) if member and member.party else None,
                "gender": member.gender if member else None,
            },
        }
        features.append(feature)

    return JsonResponse(
        {"type": "FeatureCollection", "features": features},
        json_dumps_params={'ensure_ascii': False}) # 한글 깨짐 문제 해결

def geovote_main(request):
    return render(request, 'geovote_main.html')

def map_view(request):
    return render(request, 'map.html')

# 테스트용
def map22(request):
    return render(request, 'map_22.html')
