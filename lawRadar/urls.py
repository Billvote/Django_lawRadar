"""
URL configuration for lawRadar project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls. static import static
from django.conf import settings
from billview import views as bill_v
from main import views as main_v
from geovote import views as geovote_v
from dashboard import views as dashboard_v
from history import views as history_v
from cardnews import views as cardnews_v


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # home
    path('', main_v.home, name='home'),
    # about us
    path('aboutUs/', main_v.aboutUs, name='about'),
    # search
    path('search/', main_v.search, name='search'),
    path("galaxy/", main_v.cluster_galaxy_view, name="cluster_galaxy"),
    path("api/cluster_keywords/", main_v.cluster_keywords_json, name="cluster_keywords_json"),

    # billview
    path('billview/', bill_v.index_bill, name='index'),
    path('billview/<int:id>/', bill_v.detail_bill, name='detail'),

    # tree map
    path('treemap/', geovote_v.treemap_view, name='treemap'),
    path('api/treemap-data/', geovote_v.region_tree_data, name='treemap_data_api'),
    path('api/region-tree/', geovote_v.region_tree_data, name='region_tree_data'),
    path('api/member-vote-summary/', geovote_v.member_vote_summary_api, name='member_vote_summary_api'),
    path('api/member-alignment/', geovote_v.member_alignment_api, name='member_alignment_api'),
    
    # dashboard
    path('dashboard/<int:congress_num>', dashboard_v.dashboard, name='dashboard'),
    path('api/cluster_chart/', dashboard_v.cluster_chart_api, name='cluster_chart_api'),

    # history
    path('history/', include('history.urls')),

    # card news
    path('cardnews/', include('cardnews.urls')),

    # 검색 자동완성 -------------------------------
    path("api/autocomplete/", main_v.autocomplete, name="autocomplete"),


]