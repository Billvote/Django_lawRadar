import django, os, sys
from pathlib import Path
# BASE_DIR 설정
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))  # 루트 폴더를 path에 추가
# settings 불러오기
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lawRadar.settings")  # 프로젝트 폴더 이름.settings
import django
django.setup()

from django.conf import settings
import pandas as pd

# from data_pipeline.crawling._01_save_bill_ids import fetch_and_save_bill_ids
# from data_pipeline.crawling._02_result_vote_crawling import collect_vote_data
# from data_pipeline.crawling._03_bill_summary_crawling import crawl_summaries
# from data_pipeline.cluster._01_keyword_gemini import legal_specialized_processing_system

from geovote.models import Age, Vote, Member
from billview.models import Bill
from data_pipeline.clustering.cluster_label import assign_existing_cluster_and_label

base_path = settings.BASE_DIR / 'data_pipeline'

def safe_str(x):
    return str(x) if x is not None else ''

def run_all(eraco: str):
    # 출력 옵션 설정: 모든 행과 열, 셀 최대 길이 제한 해제
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_colwidth', None)

    # 1. 신규 법안 필터링
    df = pd.read_csv("data/04_cleaned_df.csv", encoding='utf-8-sig')
    existing_bill_ids = set(Bill.objects.values_list('bill_id', flat=True))
    df_new = df[~df['bill_id'].isin(existing_bill_ids)].copy() # 신규 법안만 추리기

    if df_new.empty:
        print("신규 법안 없음")
        return

    # 기존 db df 형태로 가져오기
    existing_qs = Bill.objects.values('title', 'cleaned', 'cluster', 'cluster_keyword', 'label')
    existing_df = pd.DataFrame(list(existing_qs))

    # 2. cluster, label 할당
    df_new_cluster_label = assign_existing_cluster_and_label(df_new, existing_df.to_dict('records'))

    # 3. db 저장
    # 3-1. bill
    # 필요 컬럼만 선택
    bill_columns = [
    'bill_id', 'bill_number', 'title', 'cleaned', 'summary',
    'cluster', 'cluster_keyword', 'label', 'url', 'card_news_content'
    ]
    df_for_bill = df_new_cluster_label[bill_columns].copy()

    age_obj = Age.objects.filter(number=int(eraco)).first()
    if not age_obj:
        print(f"해당하는 대수({eraco})의 Age 객체가 없습니다.")
        return

    created, skipped = 0, 0
    for _, row in df_for_bill.iterrows():
        try:
            bill_id = safe_str(row['bill_id'])
            bill_number = safe_str(row['bill_number'])

            defaults = {
                'title': safe_str(row['title']),
                'age': age_obj,
                'cleaned': safe_str(row.get('cleaned')) or None,
                'summary': safe_str(row.get('summary')) or None,
                'cluster': int(row['cluster']) if pd.notna(row['cluster']) else None,
                'cluster_keyword': safe_str(row.get('cluster_keyword')),
                'label': int(row['label']) if pd.notna(row.get('label')) else None,
                'url': safe_str(row.get('url')) or None,
                'card_news_content': safe_str(row.get('card_news_content')) or None,
            }

            _, created_flag = Bill.objects.update_or_create(
                bill_id=bill_id,
                defaults={**defaults, 'bill_number': bill_number}
            )

            if created_flag:
                created += 1
            else:
                skipped += 1

        except Exception as e:
            print(f"[ERROR] 저장 실패: {e}, row={row.to_dict()}")
            skipped += 1
    print(f"[BILL] 신규 생성: {created}건, 업데이트(기존): {skipped}건")

    # 3-2. vote
    # 필요 컬럼만 선택
    vote_columns = [
    'age', 'member_id', 'bill_number', 'result', 'date'
    ]
    df_for_vote = df_new_cluster_label[vote_columns].copy()

    created, skipped = 0, 0

    for _, row in df_for_vote.iterrows():
        try:
            # 외래키 객체 찾기
            member_obj = Member.objects.filter(id=row['member_id']).first()
            bill_obj = Bill.objects.filter(bill_id=row['bill_id']).first()

            if not member_obj or not bill_obj:
                print(f"Member 또는 Bill 객체 없음 (member_id: {row['member_id']}, bill_id: {row['bill_id']})")
                skipped_count += 1
                continue

            vote_obj, created = Vote.objects.update_or_create(
                age=age_obj,
                member=member_obj,
                bill=bill_obj,
                date=row['date'],
                defaults={
                    'result': row['result'],
                }
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        except Exception as e:
            print(f"[ERROR] Vote 저장 실패: {e}, row={row.to_dict()}")
            skipped_count += 1

    print(f"[VOTE] 신규 생성: {created_count}건, 업데이트/스킵: {skipped_count}건")

    
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용 예시: python run_pipeline.py 22")
        sys.exit(1)

    congress_number = sys.argv[1]

    if not congress_number.isdigit():
        print("오류: 대수는 숫자여야 합니다.")
        sys.exit(1)

    run_all(congress_number)
