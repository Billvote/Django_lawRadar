# import pandas as pd
# import re

# # CSV 파일 로드
# df = pd.read_csv("data/district.csv")

# # 'SGG'에서 '갑', '을', '병', '정' 제거
# def clean_sgg(sgg_name):
#     return re.sub(r'(갑|을|병|정)$', '', sgg_name)

# # 복합 선거구 처리 ('구', '군', '시' 제거, 단어 수 1개이며 5자 이상인 경우만)
# def clean_suffix(name):
#     if ' ' not in name and len(name) >= 5:
#         return re.sub(r'(구|군|시)$', '', name)
#     return name

# # SIDO_SGG 갱신: SGG 값을 정제한 후, 그것을 SIDO_SGG에 덮어쓰기
# df['SIDO_SGG'] = df['SGG'].apply(clean_sgg).apply(clean_suffix)

# # 결과 저장 (컬럼 순서 유지)
# df.to_csv("cleaned_districts.csv", index=False, columns=["SGG_Code", "SIDO_SGG", "SIDO", "SGG", "boundary"])

# # 결과 확인 (선택)
# print(df[['SIDO', 'SGG', 'SIDO_SGG']].head())

import pandas as pd

# CSV 파일 불러오기
df = pd.read_csv("data/district.csv")  # 파일 경로를 실제 경로로 수정하세요

# 중복된 SGG 값 리스트만 추출
dup_sgg_list = df['SGG'][df['SGG'].duplicated()].unique()

print("중복된 SGG 값들:")
print(dup_sgg_list)