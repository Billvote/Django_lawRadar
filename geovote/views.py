from django.shortcuts import render
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from .models import District
import json

# geojson api
def district_geojson(request):
    districts = District.objects.all()

    features = []
    for d in districts:
        member = d.member_set.first() # 한 명만 표시
        features.append({
            "type": "Feature",
            "geometry": d.boundary,  # GeoJSON geometry
            "properties": {
                "id": d.id,
                "SGG_Code": d.SGG_Code,
                "SIDO_SGG": d.SIDO_SGG,
                "SIDO": d.SIDO,
                "SGG": d.SGG,
                "member_name": member.name if member else None,
                "party": str(member.party) if member else None,
                "gender": member.gender if member and member.party else None,
            }
        })
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return JsonResponse(geojson, encoder=DjangoJSONEncoder)

def geovote_main(request):
    return render(request, 'geovote_main.html')

def map_view(request):
    return render(request, 'map.html')
