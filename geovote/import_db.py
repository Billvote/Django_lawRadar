from tqdm import tqdm
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

# ---------- Helper Functions ----------
def safe_str(val):
    return str(val).strip() if not pd.isna(val) else ""

def get_age_instance(age_number):
    return Age.objects.get(number=age_number)

def get_or_none(dict_, key):
    return dict_.get(key, None)

# ---------- 1. Age ----------
def import_ages(csv_path):
    """
    csv_path에 있는 age 데이터(age number)들을 DB에 import.
    중복된 number는 건너뜀.
    """
    df = pd.read_csv(csv_path)
    created, skipped = 0, 0

    for _, row in df.iterrows():
        number = int(row['number'])
        obj, created_flag = Age.objects.get_or_create(number=number)
        if created_flag:
            created += 1
        else:
            skipped += 1

    print(f"[AGE] 신규 {created}개, 업데이트 {skipped}개")

# ---------- 2. Party ----------
def import_parties(csv_path):
    df = pd.read_csv(csv_path)
    created, skipped = 0, 0

    for _, row in df.iterrows():
        name = safe_str(row['party'])
        color = safe_str(row.get('color')) or '#000000'
        obj, created_flag = Party.objects.get_or_create(party=name, defaults={'color': color})
        if created_flag:
            created += 1
        else:
            skipped += 1

    print(f"[PARTY] 신규 {created}개, 업데이트 {skipped}개")

# ---------- 3. District ----------
def import_districts(csv_path):
    df = pd.read_csv(csv_path)
    created, skipped = 0, 0

    for _, row in df.iterrows():
        code = row['SGG_Code']
        defaults = {
            'SIDO_SGG': row['SIDO_SGG'],
            'SIDO': row['SIDO'],
            'SGG': row['SGG'],
            'SIGUNGU': row['SIGUNGU'],
        }
        obj, created_flag = District.objects.update_or_create(SGG_Code=code, defaults=defaults)
        if created_flag:
            created += 1
        else:
            skipped += 1

    print(f"[DISTRICT] 신규 {created}개, 업데이트 {skipped}개")

# ---------- 4. Member ----------
def import_members(csv_path):
    df = pd.read_csv(csv_path)
    age_dict = {a.number: a for a in Age.objects.all()}
    party_dict = {p.party: p for p in Party.objects.all()}
    district_dict = {d.SIDO_SGG: d for d in District.objects.all()}

    created, skipped = 0, 0

    for _, row in df.iterrows():
        age_number = int(row['age'])
        member_id = safe_str(row['member_id'])

        defaults = {
            'name': safe_str(row['name']),
            'party': party_dict.get(safe_str(row['party'])),
            'gender': safe_str(row['gender']),
            'district': district_dict.get(safe_str(row.get('SIDO_SGG'))),
            'image_url': safe_str(row.get('image_url')) or None,
        }

        age = age_dict.get(age_number)
        if not age or not defaults['party']:
            print(f"[SKIP] FK 누락 - age or party 없음: {row.to_dict()}")
            skipped += 1
            continue

        obj, created_flag = Member.objects.update_or_create(
            age=age, member_id=member_id,
            defaults=defaults
        )
        if created_flag:
            created += 1
        else:
            skipped += 1

    print(f"[MEMBER] 신규 {created}명, 업데이트 {skipped}명")

# ---------- 5. Bill ----------
def import_bills(csv_path):
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    age_dict = {a.number: a for a in Age.objects.all()}
    created, skipped = 0, 0

    for _, row in df.iterrows():
        bill_id = safe_str(row['bill_id'])
        bill_number = safe_str(row['bill_number'])

        try:
            age = age_dict.get(int(row['age']))
            if not age:
                print(f"[SKIP] 유효하지 않은 age: {row['age']}")
                skipped += 1
                continue

            defaults = {
                'title': safe_str(row['title']),
                'age': age,
                'cleaned': safe_str(row.get('cleaned')) or None,
                'summary': safe_str(row.get('summary')) or None,
                'cluster': int(row['cluster']),
                'cluster_keyword': safe_str(row.get('cluster_keyword')),
                'label': int(float(row['label'])) if not pd.isna(row.get('label')) else None,
                'url': safe_str(row.get('url')) or None,
            }

            obj, created_flag = Bill.objects.update_or_create(
                bill_id=bill_id,
                defaults={**defaults, 'bill_number': bill_number}
            )
            if created_flag:
                created += 1
            else:
                skipped += 1

        except Exception as e:
            print(f"[ERROR] 법안 처리 실패: {e}, row={row.to_dict()}")
            skipped += 1

    print(f"[BILL] 신규 {created}개, 업데이트 {skipped}개")

# ---------- 6. Vote ----------
def import_votes(csv_path):
    df = pd.read_csv(csv_path)

    # 필요 객체 캐싱
    member_dict = {
        (m.age.number, m.member_id): m for m in Member.objects.select_related('age')
    }
    bill_dict = {b.bill_number: b for b in Bill.objects.all()}

    to_create = []
    to_update = []
    skipped = 0

    # 미리 기존 Vote들 불러와서 캐싱
    existing_votes = Vote.objects.all().select_related('member', 'age', 'bill')
    vote_lookup = {
        (v.age_id, v.member_id, v.bill_id): v for v in existing_votes
    }

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Importing votes"):
        try:
            age_number = int(row['age'])
            member_id = safe_str(row['member_id'])
            bill_number = safe_str(row['bill_number'])

            member = member_dict.get((age_number, member_id))
            bill = bill_dict.get(bill_number)

            if not member or not bill:
                skipped += 1
                continue

            key = (member.age_id, member.id, bill.id)
            result = safe_str(row['result'])
            date = pd.to_datetime(row['date']).date()

            if key in vote_lookup:
                vote = vote_lookup[key]
                vote.result = result
                vote.date = date
                to_update.append(vote)
            else:
                vote = Vote(
                    age=member.age,
                    member=member,
                    bill=bill,
                    result=result,
                    date=date
                )
                to_create.append(vote)
        except Exception as e:
            print(f"[ERROR] 표결 처리 실패: {e}, row={row.to_dict()}")
            skipped += 1

    # 한 번에 업데이트 및 생성
    with transaction.atomic():
        Vote.objects.bulk_update(to_update, ['result', 'date'], batch_size=1000)
        Vote.objects.bulk_create(to_create, batch_size=1000)

    print(f"[VOTE] 신규 {len(to_create)}개, 업데이트 {len(to_update)}개, 실패 {skipped}개")

# ----------< 실행 >-------------------------
# 사용법: geovote 폴더 이동 -> 터미널에 `python import_db.py` 입력

def run_all():
    print(f'데이터 임포트 시작')

    csv_path = settings.BASE_DIR / 'geovote' / 'data'
    
    import_ages(csv_path / f'age.csv')
    import_parties(csv_path / f'party.csv')
    import_districts(csv_path / f'district.csv')
    import_members(csv_path / f'member.csv')
    import_bills(csv_path / f'bill(4).csv')
    import_votes(csv_path / f'vote.csv')

    print(f"✅ 데이터 임포트 완료")

if __name__ == "__main__":
    run_all()

