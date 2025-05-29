import json

# topojson 파일 읽기
with open('topo.json', 'r', encoding='utf-8') as f:
    topo = json.load(f)

# topojson -> geojson 수동 변환 (간단히 features만 꺼내기)
geojson = {
    "type": "FeatureCollection",
    "features": topo['objects']['precincts']['geometries']
}

# properties, geometry 등이 topojson 형식이라 완벽하지 않을 수 있음
# 따라서 Node.js topojson-client 사용 권장

with open('output_geo.json', 'w', encoding='utf-8') as f:
    json.dump(geojson, f, ensure_ascii=False, indent=2)
