import pandas as pd
import re

# CSV 파일 로드
df = pd.read_csv("data/district.csv")

# 'SGG'에서 '갑', '을', '병', '정' 제거
def clean_sgg(sgg_name):
    return re.sub(r'(갑|을|병|정)$', '', sgg_name)

# 복합 선거구 처리 ('구', '군', '시' 제거, 단어 수 1개이며 5자 이상인 경우만)
def clean_suffix(name):
    if ' ' not in name and len(name) >= 5:
        return re.sub(r'(구|군|시)$', '', name)
    return name

# 새 컬럼 'SIGUNGU' 생성
df['SIGUNGU'] = df['SGG'].apply(clean_sgg).apply(clean_suffix)

# 저장
df.to_csv("newdistricts.csv", index=False)

# 확인
print(df[['SIDO', 'SGG', 'SIDO_SGG', 'SIGUNGU']].head())

