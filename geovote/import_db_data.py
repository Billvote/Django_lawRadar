import pandas as pd
import json

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lawRadar.settings")

import django
django.setup()

from django.conf import settings
from geovote.models import District, Member, Party

# 지역구 --------------------------------------------------------------
# file_path = settings.BASE_DIR / 'geovote' / 'data' / 'boundary.csv'
# df = pd.read_csv(file_path)

# records = []
# for _, row in df.iterrows():
#     boundary = json.loads(row['boundary'])
#     records.append(District(
#         SGG_Code=row['SGG_Code'],
#         SIDO_SGG=row['SIDO_SGG'],
#         SIDO=row['SIDO'],
#         SGG=row['SGG'],
#         boundary=boundary
#     ))

# District.objects.bulk_create(records)

# 의원 ------------------------------------------------------------------
file_path = settings.BASE_DIR / 'geovote' / 'data' / 'member.csv'
df = pd.read_csv(file_path)

records = []
for _, row in df.iterrows():

    # 동일 의원이 재선 시, 건너뛰기
    age = row['age']
    if Member.objects.filter(age=age, member_id=row['member_id']).exists():
        continue
    
    party = Party.objects.get(party=row['party'])
    district = District.objects.get(SIDO_SGG=row['SIDO_SGG'])

    try:
        district = District.objects.get(SIDO_SGG=row['SIDO_SGG'])
    except District.DoesNotExist: # 지역구 매칭 안 되면 건너뜀
        continue

    member = Member(
        age=row['age'],
        name=row['name'],
        party=party,
        district=district,
        member_id=row['member_id'],
        gender=row['gender'],
    )
    records.append(member)

Member.objects.bulk_create(records) # DB 저장