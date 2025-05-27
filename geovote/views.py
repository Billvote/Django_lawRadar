from django.shortcuts import render
from django.http import JsonResponse
from .models import District
import json

# def districts_geojson(request):
    # features = []
    # for district in District.objects.all():
    #     features.append({
    #         "type": "Feature",
    #         "geometry": json.loads(district.boundary),  # 문자열 → dict
    #         "properties": {
    #             "SGG_Code": district.SGG_Code,
    #             "SIDO_SGG": district.SIDO_SGG,
    #             "SIDO": district.SIDO,
    #             "SGG": district.SGG,
    #         }
    #     })

    # geojson = {
    #     "type": "FeatureCollection",
    #     "features": features
    # }

    # return JsonResponse(geojson)

def geovote_main(request):
    return render(request, 'geovote_main.html')

def map_view(request):
    return render(request, 'map.html')
