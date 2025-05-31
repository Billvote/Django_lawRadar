import pandas as pd
import json

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lawRadar.settings")

import django
django.setup()

from django.db import transaction
from django.conf import settings
from geovote.models import District, Member, Party, Age, Vote
from billview.models import Bill

# 의안
def import_bills(csv_path):
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

# 1) 지역구
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


# 2) 의원(수정 필요: 20대 지역구가 22대 geojson과 맞지 않는 문제 있음)
def import_members(csv_path):
    df = pd.read_csv(csv_path)

    # FK 참조 테이블 캐싱
    age_dict = {age.number: age for age in Age.objects.all()}
    party_dict = {p.party: p for p in Party.objects.all()}
    district_dict = {d.SIDO_SGG: d for d in District.objects.all()}

    # 기존 (age_id, member_id) 조합 캐싱 (중복 검사)
    existing_members = set(
        Member.objects.values_list('age__number', 'member_id')
    )

    records = []

    for _, row in df.iterrows():
        try:
            age_number = int(row['age'])
            member_id = str(row['member_id']).strip()
            name = str(row['name']).strip()
            party_name = str(row['party']).strip()
            gender = str(row['gender']).strip()
            sido_sgg = str(row.get('SIDO_SGG', '')).strip()

            # 중복 검사
            if (age_number, member_id) in existing_members:
                continue

            # FK 조회
            age = age_dict.get(age_number)
            party = party_dict.get(party_name)

            if not age or not party:
                print(f"[SKIP] 누락된 FK - age: {age}, party: {party_name} ({name})")
                continue

            # 지역구 처리
            district = None
            if sido_sgg and sido_sgg != "<비례대표>":
                district = district_dict.get(sido_sgg)
                if not district:
                    print(f"[WARN] 지역구 없음: {sido_sgg} ({name})")

            records.append(Member(
                age=age,
                name=name,
                party=party,
                district=district,
                member_id=member_id,
                gender=gender,
            ))

        except Exception as e:
            print(f"[ERROR] 처리 중 오류 발생 (row: {row.to_dict()}): {e}")
            continue

    # bulk insert
    if records:
        with transaction.atomic():
            Member.objects.bulk_create(records, batch_size=1000)
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
        color = row.get('color', '#000000').strip()

        if name and name not in existing_parties:
            records.append(Party(party=name, color=color))
        else:
            print(f"[SKIP] 이미 존재하는 정당명: {name}")

    Party.objects.bulk_create(records)
    print(f"[DONE] {len(records)}개의 정당 저장 완료")

# 4) 표결------------------------------------------
def import_votes(csv_path):
    df = pd.read_csv(csv_path)

    # FK 테이블 미리 캐싱
    member_dict = {
        (m.age.number, m.member_id): m
        for m in Member.objects.select_related('age')
    }
    bill_dict = {
        b.bill_number: b
        for b in Bill.objects.all()
    }

    # 중복 투표 방지용 기존 키 로드
    existing_votes = set(
        Vote.objects.values_list('age__number', 'member__member_id', 'bill__bill_number')
    )

    records = []

    for _, row in df.iterrows():
        try:
            age_num = int(row['age'])
            member_id = str(row['member_id']).strip()
            bill_number = str(row['bill_number']).strip()
            result = str(row['result']).strip()
            date = pd.to_datetime(row['date']).date()

            vote_key = (age_num, member_id, bill_number)

            if vote_key in existing_votes:
                continue

            member = member_dict.get((age_num, member_id))
            bill = bill_dict.get(bill_number)

            if not member or not bill:
                print(f"[SKIP] FK 없음 - member: {member}, bill: {bill_number}")
                continue

            records.append(Vote(
                age=member.age,
                member=member,
                bill=bill,
                result=result,
                date=date,
            ))

        except Exception as e:
            print(f"[ERROR] 처리 중 오류 발생 (row: {row.to_dict()}): {e}")
            continue

    # bulk insert
    if records:
        with transaction.atomic():
            Vote.objects.bulk_create(records, batch_size=1000)
        print(f"[DONE] {len(records)}개의 투표 내역 저장 완료.")
    else:
        print("[INFO] 저장할 신규 투표 데이터가 없습니다.")


# ----------< 실행 >-------------------------
# 참고) age -> party -> district -> member -> vote 순으로 실행해야 함

csv_path = settings.BASE_DIR / 'geovote' / 'data' / 'age.csv'
import_ages(csv_path)