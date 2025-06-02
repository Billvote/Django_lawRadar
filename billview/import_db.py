import pandas as pd
import json

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lawRadar.settings")

import django
django.setup()

from django.conf import settings
from billview.models import Bill
from geovote.models import Age
from django.db import transaction

def import_bills(csv_path):
    df = pd.read_csv(csv_path)

    # FK 및 중복 캐싱
    age_dict = {age.number: age for age in Age.objects.all()}
    existing_bill_ids = set(Bill.objects.values_list('bill_id', flat=True))
    existing_bill_numbers = set(Bill.objects.values_list('bill_number', flat=True))

    records = []
    for _, row in df.iterrows():
        try:
            cluster_value = int(row['cluster'])
            bill_id = str(row['bill_id']).strip()
            bill_number = str(row['bill_number']).strip()

            if bill_id in existing_bill_ids or bill_number in existing_bill_numbers:
                print(f"[SKIP] 중복 법안: bill_id={bill_id}, bill_number={bill_number}")
                continue

            age = age_dict.get(int(row['age']))
            if not age:
                print(f"[SKIP] 유효하지 않은 age: {row['age']}")
                continue

            summary = str(row.get('summary', '')).strip()
            summary = summary if summary and not pd.isna(summary) else None

            # cluster_keyword = str(row.get('cluster_keyword', '')).strip()
            raw_keyword = row.get('cluster_keyword')
            if pd.isna(raw_keyword):
                cluster_keyword = ''
            else:
                cluster_keyword = raw_keyword.strip()

            records.append(Bill(
                age=age,
                title=str(row['title']).strip(),
                bill_id=bill_id,
                bill_number=bill_number,
                summary=summary,
                cluster=int(row['cluster']),
                cluster_keyword=cluster_keyword
            ))

        except Exception as e:
            print(f"[ERROR] 행 처리 실패: {e} (row={row.to_dict()})")
            continue
    
    if records:
        Bill.objects.bulk_create(records, batch_size=1000)
        print(f"[DONE] {len(records)}개의 법안 저장 완료")
    else:
        print("[INFO] 저장할 법안이 없습니다.")


# 실행
csv_path = settings.BASE_DIR / 'geovote' / 'data' / 'bill(1).csv'
import_bills(csv_path)

# df = pd.read_csv(csv_path)
# # print(df.info())
# print(df['cluster_keyword'].value_counts())
