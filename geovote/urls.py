
from django.urls import path
from . import views

urlpatterns = [
    path('treemap/', views.treemap_view, name='treemap'),
    path('api/treemap-data/', views.region_tree_data, name='api_treemap_data'),
    path('api/member-vote-summary/', views.member_vote_summary_api, name='api_member_vote_summary'),
    path('api/member-alignment/', views.member_alignment_api, name='api_member_alignment'),
    # path('api/member-like/', views.member_like_api, name='member_like_api'),
    path('planb/', views.planb_view, name='planb'),
]
