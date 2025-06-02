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
from geovote import views as geovote_views
from billview import views as bill_views
from main import views as main_views
from geovote import views as geovote_views
from dashboard import views as dashboard_v
from history import views as history_v


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', main_views.home, name='home'),

    # billview
    path('billview/', bill_views.index_bill, name='index'),
    path('billview/<int:id>/', bill_views.detail_bill, name='detail'),

    # geovote
    # path('map/', geovote_views.map_view, name='map'),
    path('geovote/', geovote_views.geovote_main, name='geovote'),

    # path('api/districts/', geovote_views.district_geojson, name='district_geojson'),
    # path('map22/', geovote_views.map22, name='map22'), # 테스트용

    path('treemap/', geovote_views.treemap_view, name='treemap'),
    path('api/region_tree_data/', geovote_views.region_tree_data, name='region_tree_data'),
    
    # dashboard
    path('dashboard/<int:congress_num>', dashboard_v.dashboard, name='dashboard'),

    # history
    path('history/<int:id>/', history_v.detail_history, name='history'),
]