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
# from geovote import views
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
    path('', include(('main.urls', 'main'), namespace='main')),

    # billview
    path('billview/', bill_v.index_bill, name='index'),
    path('billview/<int:id>/', bill_v.detail_bill, name='detail'),

    # tree map
    path('geovote/', include('geovote.urls')),
    
    # dashboard
    path('dashboard/', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),

    # history
    path('history/', include('history.urls')),

    # card news
    path('cardnews/', include('cardnews.urls')),

    # 검색 자동완성 -------------------------------
    path("api/autocomplete/", main_v.autocomplete, name="autocomplete"),

    # 로그인
    path('accounts/', include('accounts.urls')),

]