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
from pathlib import Path

import glob

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
        sido_sgg = row['SIDO_SGG']
        defaults = {
            'age': row['age'],
            'SIDO': row['SIDO'],
            'SGG': row['SGG'],
            'SIGUNGU': row['SIGUNGU'],
        }
        # SIDO_SGG 기준으로 update_or_create
        obj, created_flag = District.objects.update_or_create(SIDO_SGG=sido_sgg, defaults=defaults)
        if created_flag:
            created += 1
        else:
            skipped += 1

    print(f"[DISTRICT] 신규 {created}개, 업데이트 {skipped}개")

# -----------------지역구-의원 매칭 실패 데이터 확인 -------------------

def check_missing_sido_sgg(csv_path):
    df = pd.read_csv(csv_path)

    # CSV에서 SIDO_SGG 값 추출 및 정리
    csv_sido_sgg_set = set(df['SIDO_SGG'].dropna().map(str.strip))

    # District 테이블에서 등록된 SIDO_SGG 목록
    db_sido_sgg_set = set(District.objects.values_list('SIDO_SGG', flat=True))

    # 차집합 → 매칭 실패한 값
    unmatched = csv_sido_sgg_set - db_sido_sgg_set

    print(f"\n❗ 매칭 실패한 지역구 (SIDO_SGG): {len(unmatched)}개")
    for sido_sgg in sorted(unmatched):
        print(f"- {sido_sgg}")

# ---------- 4. Member ----------
def import_members(csv_path):
    df = pd.read_csv(csv_path)
    age_dict = {a.number: a for a in Age.objects.all()}
    party_dict = {p.party: p for p in Party.objects.all()}
    district_dict = {d.SIDO_SGG: d for d in District.objects.all()}

    created, updated, skipped = 0, 0, 0

    def safe_str(value):
        if pd.isna(value) or value is None:
            return ''
        return str(value).strip()

    for _, row in df.iterrows():
        age_number = int(row['age'])
        member_id = safe_str(row['member_id'])

        # district 처리
        sido_sgg_raw = safe_str(row.get('SIDO_SGG'))
        district = None
        if sido_sgg_raw and sido_sgg_raw != "<비례대표>":
            district = district_dict.get(sido_sgg_raw)

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
            age=age,
            member_id=member_id,
            defaults=defaults
        )
        if created_flag:
            created += 1
        else:
            updated += 1

    print(f"[MEMBER] 신규 {created}명, 업데이트 {updated}명, 스킵 {skipped}명")

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
                'card_news_content': safe_str(row.get('card_news_content')) or None,
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
def import_votes(df, member_dict, bill_dict):

    keys = [
        (int(row.age), safe_str(row.member_id), safe_str(row.bill_number))
        for row in df.itertuples()
    ]
    # DB에서 이 chunk에 해당하는 기존 Vote만 조회
    existing_votes_qs = Vote.objects.filter(
        age__number__in=[k[0] for k in keys],
        member__member_id__in=[k[1] for k in keys],
        bill__bill_number__in=[k[2] for k in keys]
    ).select_related('member', 'age', 'bill')

    vote_lookup = {
        (v.age.number, v.member.member_id, v.bill.bill_number): v for v in existing_votes_qs
    }

    to_create = []
    to_update = []
    skipped = 0

    for row in df.itertuples():
        try:
            age_number = int(row.age)
            member_id = safe_str(row.member_id)
            bill_number = safe_str(row.bill_number)

            member = member_dict.get((age_number, member_id))
            bill = bill_dict.get(bill_number)

            if not member or not bill:
                skipped += 1
                continue

            key = (age_number, member_id, bill_number)
            result = safe_str(row.result)
            date = pd.to_datetime(row.date).date()

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
            skipped += 1
            continue

    # 한 번에 업데이트 및 생성
    with transaction.atomic():
        if to_update:
            Vote.objects.bulk_update(to_update, ['result', 'date'], batch_size=10000)
        if to_create:
            Vote.objects.bulk_create(to_create, batch_size=10000)

    print(f"[VOTE] 신규 {len(to_create)}개, 업데이트 {len(to_update)}개, 실패 {skipped}개")


# ----------< 실행 >-------------------------
# 사용법: geovote 폴더 이동 -> 터미널에 `python import_db.py` 입력

def run_all():
    print(f'데이터 임포트 시작')

    csv_path = settings.BASE_DIR / 'geovote' / 'data'
    
    import_ages(csv_path / f'age.csv')
    import_parties(csv_path / f'party.csv')
    import_districts(csv_path / f'district.csv')
    check_missing_sido_sgg(csv_path / f'member.csv') # 매칭 실패한 지역구 찾기
    import_members(csv_path / f'member.csv')
    import_bills(csv_path / f'bill.csv')
    
    # vote import하기
    # vote_csv_path = csv_path / 'vote.csv'
    # chunk_size = 1000  # 1000줄씩 읽기
    # member_dict = {
    #     (m.age.number, m.member_id): m for m in Member.objects.select_related('age')
    # }
    # bill_dict = {b.bill_number: b for b in Bill.objects.all()}
    # for i, chunk in enumerate(pd.read_csv(vote_csv_path, chunksize=chunk_size)):
    #     print(f'📥 importing chunk {i}')
    #     import_votes(
    #         chunk,
    #         member_dict=member_dict,
    #         bill_dict=bill_dict,
    #         # vote_lookup=vote_lookup
    #     )
    # print(f"✅ 데이터 임포트 완료")

if __name__ == "__main__":
    run_all()

