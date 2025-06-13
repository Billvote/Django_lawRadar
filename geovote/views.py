from django.shortcuts import render
from django.http import JsonResponse
from .models import Age, Member, District
from collections import defaultdict

def treemap_view(request):
    ages = Age.objects.all().order_by('number')
    return render(request, 'treemap.html', {'ages': ages})


def region_tree_data(request):
    age_id = request.GET.get('age')
    if not age_id:
        return JsonResponse({"error": "age parameter is required"}, status=400)

    try:
        age_id = int(age_id)
        age_obj = Age.objects.get(id=age_id)
    except (ValueError, Age.DoesNotExist):
        return JsonResponse({"error": "Invalid age parameter"}, status=400)

    members = Member.objects.filter(age=age_obj).select_related('party', 'district')
    member_dict = {m.district_id: m for m in members if m.district_id}

    districts = District.objects.filter(id__in=member_dict.keys())

    tree = defaultdict(lambda: defaultdict(list))
    for district in districts:
        sido = district.SIDO or "기타"
        sigungu = district.SIGUNGU or "기타"
        tree[sido][sigungu].append(district)

    result = {
        "name": "대한민국",
        "type": "ROOT",
        "children": []
    }

    for sido_name, sigungu_map in tree.items():
        sido_node = {"name": sido_name, "type": "SIDO", "children": []}
        for sigungu_name, district_list in sigungu_map.items():
            sigungu_node = {"name": sigungu_name, "type": "SIGUNGU", "children": []}
            for district in district_list:
                member = member_dict.get(district.id)
                if member:
                    label = f"{district.SGG}\n({member.name} - {member.party.party})"
                    color = member.party.color
                else:
                    label = f"{district.SGG} (의원 없음)"
                    color = "#cccccc"
                sigungu_node["children"].append({
                    "id": district.id,
                    "member_name": member.name if member else None,
                    "image_url": member.image_url if member else None,
                    "name": label,
                    "type": "District",
                    "value": 1,
                    "color": color
                })
            sido_node["children"].append(sigungu_node)
        result["children"].append(sido_node)

    return JsonResponse(result)

#----------------------의원 - 의안 클러스터 - 표결 연결 ------------------
from django.http import JsonResponse
from django.db.models import Count
from .models import Vote
from billview.models import Bill

def member_vote_summary_api(request):
    member_name = request.GET.get('member_name')
    if not member_name:
        return JsonResponse({'error': 'member_name parameter is required'}, status=400)

    try:
        # 해당 의원의 모든 표결 결과를 가져옴 (cluster별 result 집계)
        votes = Vote.objects.filter(member__name=member_name)\
            .values('bill__cluster', 'result')\
            .annotate(count=Count('id'))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': 'Failed to fetch votes', 'details': str(e)}, status=500)

    # 클러스터 목록
    clusters = set(vote['bill__cluster'] for vote in votes)

    # 클러스터별 cluster_keyword 매핑
    cluster_keywords = {}
    for cluster in clusters:
        bill = Bill.objects.filter(cluster=cluster).first()
        cluster_keywords[cluster] = bill.cluster_keyword if bill else "알 수 없음"

    # 클러스터별 법안 개수 조회 (0 방지용으로 1로 설정해둘 수도 있음)
    cluster_bill_counts = {c: Bill.objects.filter(cluster=c).count() for c in clusters}

    # 클러스터별 투표 결과 집계 초기화
    cluster_summary = {c: {'찬성': 0, '반대': 0, '기권': 0, '불참': 0} for c in clusters}

    # 투표 결과 누적
    for vote in votes:
        cluster = vote['bill__cluster']
        result = vote['result']
        if result not in ['찬성', '반대', '기권', '불참']:
            result = '기권'  # 기타 결과는 기권으로 처리
        cluster_summary[cluster][result] += vote['count']

    # 찬성, 반대, 기권, 불참 별로 최대 클러스터 찾기 및 비율 계산
    max_clusters = {}
    for vote_type in ['찬성', '반대', '기권', '불참']:
        max_cluster = None
        max_count = -1
        for cluster, counts in cluster_summary.items():
            if counts[vote_type] > max_count:
                max_count = counts[vote_type]
                max_cluster = cluster

        if max_cluster is not None:
            bill_count = cluster_bill_counts.get(max_cluster, 1)
            counts = cluster_summary[max_cluster]
            ratios = {k: round(counts[k] / bill_count * 100, 2) if bill_count > 0 else 0 for k in ['찬성', '반대', '기권', '불참']}

            max_clusters[vote_type] = {
                'cluster': max_cluster,
                'cluster_keyword': cluster_keywords.get(max_cluster, "알 수 없음"),
                'counts': counts,
                'ratios': ratios,
                'bill_count': bill_count,
            }

    return JsonResponse(max_clusters)
























