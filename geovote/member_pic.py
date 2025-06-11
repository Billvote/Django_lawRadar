import requests
from decouple import config
import xmltodict

def fetch_member_photo_map():
    api_key = config('ASSEMBLY_API_KEY')
    url = f"http://apis.data.go.kr/9710000/NationalAssemblyInfoService/getMemberCurrStateList?ServiceKey={api_key}&numOfRows=300&pageNo=1"
    response = requests.get(url)
    response.raise_for_status()
    data = response.text

    # XML 파싱 (예시: xmltodict 또는 lxml 사용)
    parsed = xmltodict.parse(data)
    items = parsed['response']['body']['items']['item']

    photo_map = {}
    for item in items:
        name = item['NAAS_NM']
        district = item['ELECD_NM']
        photo_url = item['NAAS_PIC']
        key = f"{name}|{district}"
        photo_map[key] = photo_url

    return photo_map
