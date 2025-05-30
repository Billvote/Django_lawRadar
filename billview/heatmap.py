# visualize_votes.py

import os
import django
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Django 설정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lawRadar.settings")
django.setup()

from geovote.models import Vote

# ---- 데이터 가져오기 및 시각화 코드 작성 ----
votes = Vote.objects.select_related('bill', 'member').all()

data = [
    {
        'bill_title': v.bill.title,
        'member_name': v.member.name,
        'result': v.result
    }
    for v in votes
]

df = pd.DataFrame(data)

# 피벗
heatmap_data = df.pivot(index='member_name', columns='bill_title', values='result')

# 숫자 매핑
result_map = {'찬성': 2, '기권': 1, '반대': 0, '불참': None}
heatmap_numeric = heatmap_data.replace(result_map)

# 시각화
plt.figure(figsize=(16, 10))
sns.heatmap(
    heatmap_numeric,
    cmap=sns.color_palette(["#e74c3c", "#f1c40f", "#3498db"]),
    linewidths=0.4,
    linecolor='white',
    mask=heatmap_numeric.isna()
)
plt.xticks(rotation=90)
plt.title('의안별 국회의원 표결 히트맵')
plt.tight_layout()
plt.show()