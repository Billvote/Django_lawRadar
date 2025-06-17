from django.urls import path

from .views import (
    BillHistoryListView,     # 메인 목록 + 검색 + 페이지네이션
    BillHistoryDetailView,   # 의안 상세
    cluster_index,           # 클러스터 해시태그 클릭용 리다이렉트
    autocomplete,            # ───────────── 자동완성 JSON 엔드포인트
)

app_name = "history"

urlpatterns = [
    # 메인 페이지  ─ /history/
    path("", BillHistoryListView.as_view(), name="history_list"),

    # 의안 상세   ─ /history/bill/123/
    path("bill/<int:pk>/", BillHistoryDetailView.as_view(), name="bill_detail"),

    # 클러스터   ─ /history/cluster/17/
    #             → cluster_index 가 /?cluster=17 로 리다이렉트
    path("cluster/<int:cluster_number>/", cluster_index, name="cluster_index"),

    # 자동완성   ─ /history/autocomplete/?term=환경
    path("autocomplete/", autocomplete, name="autocomplete"),
]
