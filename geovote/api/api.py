import requests
import xmltodict  # XML을 dict로 변환해주는 라이브러리
import json

# API 요청 URL (발급받은 키, 파라미터 포함)

service_Key = 'myQHEaV7DaMcwSCZnBcZXr6cqOdY7ThQdx1E83yZNA0iMQDCp4lteon0J1Hdb3EuFgcxuieb1zSFcVVlRFf3GA=='
url = 'http://apis.data.go.kr/9760000/CommonCodeService/getCommonSgCodeList'
all_items = []
page_no = 1
while True:
    params = {
        'serviceKey': service_Key,
        ''
        'sgId': '20000413',
        'sgTypecode': '2',
        '_type': 'json',
        'pageNo': 100,
        'numOfRows': 100  # 최대한 많이
    }

    response = requests.get(url, params=params)
    # print(response.content)



    if response.status_code == 200:
        try:
            # XML → dict 변환
            data_dict = xmltodict.parse(response.content)

            # dict → JSON 저장
            with open('api/data/data.json', 'w', encoding='utf-8') as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)

            print("✅ XML 데이터를 JSON으로 저장 완료!")
        except Exception as e:
            print("❌ 변환 실패:", e)
            print(response.text)
    else:
        print("❌ 요청 실패:", response.status_code)
        print(response.text)
