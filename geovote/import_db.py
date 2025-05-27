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
from billview.models import Bill

# billview: bill (1개)
# geovote: bill, district, party, member, vote (5개)

# billview 의안---------------------
def import_billview_bills(csv_path):
    df = pd.read_csv(csv_path)

    # 중복된 bill_id와 bill_number 미리 DB에서 조회
    existing_bill_ids = set(Bill.objects.values_list('bill_id', flat=True))
    existing_bill_numbers = set(Bill.objects.values_list('bill_number', flat=True))

    records = []
    for _, row in df.iterrows():
        bill_id = str(row['bill_id']).strip()
        bill_number = str(row['bill_number']).strip()

        if bill_id in existing_bill_ids or bill_number in existing_bill_numbers:
            print(f"[SKIP] 중복 법안: bill_id={bill_id}, bill_number={bill_number}")
            continue

        records.append(Bill(
            age=row['age'],
            title=row['title'].strip(),
            bill_id=bill_id,
            bill_number=bill_number,
            content=row.get('content', '').strip() if not pd.isna(row.get('content')) else None
        ))

    Bill.objects.bulk_create(records)
    print(f"[DONE] {len(records)}개의 법안 저장 완료.")

# 1) 지역구 --------------------------------------------------------------
def import_districts(csv_path):
    df = pd.read_csv(csv_path)
    
    existing_codes = set(District.objects.values_list('SGG_Code', flat=True))
    
    records = []
    for _, row in df.iterrows():
        if row['SGG_Code'] in existing_codes:
            print(f"[SKIP] 이미 존재하는 구역: {row['SGG_Code']}")
            continue

        try:
            boundary = json.loads(row['boundary'])
        except json.JSONDecodeError:
            print(f"[SKIP] 잘못된 JSON: {row['SGG_Code']}")
            continue
        
        records.append(District(
            SGG_Code=row['SGG_Code'],
            SIDO_SGG=row['SIDO_SGG'],
            SIDO=row['SIDO'],
            SGG=row['SGG'],
            boundary=boundary
        ))

    District.objects.bulk_create(records)
    print(f"[DONE] {len(records)}개의 구역 저장 완료")


# 2) 의원(테스트용.. 수정 필요) ------------------------------------------------------------------
def import_members(csv_path):
    """
    CSV 파일에서 의원 데이터를 읽어 DB에 저장.
    이미 (age, member_id) 조합이 존재하면 건너뜀.
    party, district 외래키가 없으면 건너뜀.
    """
    df = pd.read_csv(csv_path)
    records = []

    for _, row in df.iterrows():
        age = row['age']
        member_id = row['member_id']

        # 중복 검사
        if Member.objects.filter(age=age, member_id=member_id).exists():
            print(f"[SKIP] 이미 존재하는 의원: age={age}, member_id={member_id}")
            continue

        # party FK 조회
        try:
            party = Party.objects.get(party=row['party'])
        except Party.DoesNotExist:
            print(f"[SKIP] 정당 없음: {row['party']} ({row['name']})")
            continue

        # district FK 조회
        try:
            district = District.objects.get(SIDO_SGG=row['SIDO_SGG'])
        except District.DoesNotExist:
            print(f"[SKIP] 지역구 없음: {row['SIDO_SGG']} ({row['name']})")
            continue

        member = Member(
            age=age,
            name=row['name'],
            party=party,
            district=district,
            member_id=member_id,
            gender=row['gender'],
        )
        records.append(member)

    if records:
        with transaction.atomic():
            Member.objects.bulk_create(records)
        print(f"[DONE] {len(records)}명의 의원 저장 완료.")
    else:
        print("[INFO] 저장할 신규 의원 데이터가 없습니다.")

# 3) party 테이블 --------------------------------------------------------------------
def import_parties(csv_path):
    df = pd.read_csv(csv_path)
    
    # 이미 DB에 있는 정당명 셋으로 미리 조회
    existing_parties = set(Party.objects.values_list('party', flat=True))
    
    records = []
    for _, row in df.iterrows():
        name = row['party'].strip()
        if name and name not in existing_parties:
            records.append(Party(party=name))
        else:
            print(f"[SKIP] 이미 존재하는 정당명: {name}")

    Party.objects.bulk_create(records)
    print(f"[DONE] {len(records)}개의 정당 저장 완료")

# ----------< 실행 >-------------------------
csv_path = settings.BASE_DIR / 'geovote' / 'data' / 'member.csv'
import_members(csv_path)