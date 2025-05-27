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
from django.db import transaction

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

# 실행
csv_path = settings.BASE_DIR / 'geovote' / 'data' / 'bill.csv'
import_members(csv_path)