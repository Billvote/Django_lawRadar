# main/urls.py
from django.urls import path
from . import views as main_v              # views.py 전체 임포트

app_name = "main"                          # 네임스페이스

urlpatterns = [
    # Home · About
    path("",            main_v.home,     name="home"),
    path("aboutUs/",    main_v.aboutUs,  name="about"),

    # 검색
    path("search/",                     main_v.search,                name="search"),
    path("galaxy/",                     main_v.cluster_galaxy_view,   name="cluster_galaxy"),
    path("api/cluster_keywords/",       main_v.cluster_keywords_json, name="cluster_keywords_json"),
    path("api/autocomplete/",           main_v.autocomplete,          name="autocomplete"),
]
