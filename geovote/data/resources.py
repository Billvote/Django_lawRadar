import pandas as pd
import json

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lawRadar.settings")

import django
django.setup()

from django.conf import settings
from geovote.models import District

file_path = settings.BASE_DIR / 'geovote' / 'data' / 'boundary.csv'
df = pd.read_csv(file_path)

records = []
for _, row in df.iterrows():
    boundary = json.loads(row['boundary'])
    records.append(District(
        SGG_Code=row['SGG_Code'],
        SIDO_SGG=row['SIDO_SGG'],
        SIDO=row['SIDO'],
        SGG=row['SGG'],
        boundary=boundary
    ))

District.objects.bulk_create(records)