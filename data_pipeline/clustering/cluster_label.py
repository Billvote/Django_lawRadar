# assign_cluster_label.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
# from yourutils import normalize_title  # 제목 정규화 함수

import pandas as pd
import re

# title 정규화 함수
# def normalize_title(title):
#     if pd.isna(title):
#         return ''

#     title = re.sub(r'\([^)]*\)', '', title) # 괄호 및 괄호 안 내용 제거
#     title = re.sub(r'[^\w\s]', '', title) # 특수문자 제거
#     title = re.sub(r'\d+차', '차', title) # 숫자+차 → 차로 통일 (예: 1차, 2차 등)
#     title = re.sub(r'\s+', ' ', title).strip() # 공백 정규화
#     return title

def assign_existing_cluster_and_label(df_new: pd.DataFrame, existing_data: list, threshold: float = 0.85):
    """
    기존 데이터와 유사도 기반으로 클러스터/라벨을 매칭해주는 함수

    Parameters:
        df_new: 새로운 데이터프레임 (title 컬럼 필수)
        existing_data: [{title, cluster, label} 형태의 딕셔너리 리스트]
        threshold: 유사도 기준 (0~1)

    Returns:
        df_new에 cluster, label 컬럼이 추가된 결과 DataFrame
    """
    df_new = df_new.copy()

    # 1. 클러스터/라벨 번호 시작점 정의
    existing_clusters = [item['cluster'] for item in existing_data if item['cluster'] is not None]
    existing_labels = [item['label'] for item in existing_data if item['label'] is not None]

    next_cluster = max(existing_clusters, default=-1) + 1
    next_label = max(existing_labels, default=-1) + 1

    # cluster - cluster_keyword 매핑 딕셔너리 구성
    cluster_keyword_map = {}
    for item in existing_data:
        c = item.get('cluster')
        kw = item.get('cluster_keyword')
        if c is not None and kw:
            cluster_keyword_map.setdefault(c, kw)

    # 2. 클러스터링 cleaned 활용 유사도 계산
    df_new['norm_cleaned'] = df_new['cleaned']
    existing_cleaned = [item['cleaned'] for item in existing_data]

    vectorizer_cleaned = TfidfVectorizer().fit(existing_cleaned + df_new['norm_cleaned'].tolist())
    existing_vecs_cleaned = vectorizer_cleaned.transform(existing_cleaned)
    new_vecs_cleaned = vectorizer_cleaned.transform(df_new['norm_cleaned'])

    clusters = []
    cluster_keywords = []

    for i in range(len(df_new)):
        sim = cosine_similarity(new_vecs_cleaned[i], existing_vecs_cleaned)[0]
        best_idx = sim.argmax()
        if sim[best_idx] > threshold:
            # 기존 클러스터 번호 사용
            cluster = existing_data[best_idx]['cluster']
            clusters.append(cluster)

            # 기존 클러스터에 해당하는 키워드가 있으면 사용, 없으면 기본 키워드
            keyword = cluster_keyword_map.get(cluster, "법안, 개정, 시행, 정책")
            cluster_keywords.append(keyword)

        else:
            clusters.append(next_cluster)
            cluster_keywords.append("법안, 개정, 시행, 정책")
            next_cluster += 1

    # 3. 라벨용 title 유사도 계산
    # title 정규화
    def normalize_title(title):
        if pd.isna(title):
            return ''
        title = re.sub(r'\([^)]*\)', '', title)
        title = re.sub(r'[^\w\s]', '', title)
        title = re.sub(r'\d+차', '차', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    df_new['norm_title'] = df_new['title'].apply(normalize_title)
    existing_titles = [normalize_title(item['title']) for item in existing_data]

    vectorizer_title = TfidfVectorizer().fit(existing_titles + df_new['norm_title'].tolist())
    existing_vecs_title = vectorizer_title.transform(existing_titles)
    new_vecs_title = vectorizer_title.transform(df_new['norm_title'])

    labels = []
    for i in range(len(df_new)):
        sim = cosine_similarity(new_vecs_title[i], existing_vecs_title)[0]
        best_idx = sim.argmax()
        if sim[best_idx] > threshold:
            labels.append(existing_data[best_idx]['label'])
        else:
            labels.append(next_label)
            next_label += 1

    df_new['cluster'] = clusters
    df_new['label'] = labels
    df_new['cluster_keyword'] = cluster_keywords

    return df_new
