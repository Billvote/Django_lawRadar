import pandas as pd
import re

# CSV 파일 불러오기
df = pd.read_csv("data/district.csv")

# SIGUNGU = SIDO_SGG에서 SIDO 제거 + '갑', '을', '병', '정' 제거
def extract_sigungu(row):
    sido = row['SIDO'].strip()
    sido_sgg = row['SIDO_SGG'].strip()
    # SIDO 제거
    sigungu = sido_sgg.replace(sido, '', 1).strip()
    # '갑', '을', '병', '정' 제거
    sigungu = re.sub(r'(갑|을|병|정)$', '', sigungu)
    return sigungu

df['SIGUNGU'] = df.apply(extract_sigungu, axis=1)

# boundary 컬럼 제거하고 필요한 컬럼만 저장
columns_to_keep = ['SGG_Code', 'SIDO', 'SIDO_SGG', 'SGG', 'SIGUNGU']
df_cleaned = df[columns_to_keep]

# 새로운 CSV로 저장
df_cleaned.to_csv("newdistricts_cleaned.csv", index=False)

# 결과 확인
print(df_cleaned.head())



#--------------------------연결-----------------------------------
# import pandas as pd
# from geovote.models import Member, District, Age, Party

# def import_members(csv_path):
#     df = pd.read_csv(csv_path)

#     for _, row in df.iterrows():
#         # CSV의 SIDO_SGG 값으로 District 객체 찾기
#         district_obj = District.objects.filter(SIDO_SGG=row['SIDO_SGG']).first()

#         # Age, Party도 외래키면 비슷하게 처리
#         age_obj = Age.objects.get(name=row['age'])
#         party_obj = Party.objects.get(name=row['party'])

#         member = Member(
#             age=age_obj,
#             name=row['name'],
#             party=party_obj,
#             district=district_obj,  # 연결된 District 객체 넣기
#             member_id=row['member_id'],
#             gender=row['gender']
#         )
#         member.save()

# # 사용 예
# import_members('path/to/member.csv')
