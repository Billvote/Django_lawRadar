import pandas as pd

# df = pd.read_csv('bill.csv')
# df_copy = df[['cluster', 'cluster_keyword']]

# df_copy.to_csv('cluster_keywords.csv', index=False)

# df = pd.read_csv('cluster_keywords.csv')
# df_unique = df.drop_duplicates()
# # print(df_unique.head())
# # print(df_unique.shape)

# counts = df['cluster_keyword'].value_counts()
# filtered = counts[counts >= 5]

# print(filtered)

from google.ai.generativelanguage import types
from google.ai.generativelanguage import generativelanguage_v1beta2

def generate_nickname(cluster_keywords):
    # API 클라이언트 초기화
    client = generativelanguage_v1beta2.GenerationServiceClient()

    # 프로젝트 위치 등 환경변수 설정 필요
    model_name = "models/chat-bison-001"  # Gemini 공식 챗 모델

    # 클러스터 키워드를 설명하는 프롬프트 작성 (예: 3~5개 키워드 문자열)
    prompt_text = (
        f"이 키워드들을 바탕으로 한국어로 멋지고 의미 있는 별명을 1개 추천해줘. "
        f"키워드: {cluster_keywords}\n"
        f"별명:"
    )

    response = client.generate_text(
        model=model_name,
        prompt=types.TextPrompt(text=prompt_text),
        temperature=0.7,
        max_tokens=20,
    )

    nickname = response.candidates[0].output.strip()
    return nickname


if __name__ == "__main__":
    example_keywords = "의료, 수급, 인력, 위원회"
    nickname = generate_nickname(example_keywords)
    print("추천 닉네임:", nickname)