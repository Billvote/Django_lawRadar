from django.shortcuts import render
from django.http import JsonResponse
from .models import Age, Member, District
from collections import defaultdict
from billview.models import Bill

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
from main.models import VoteSummary

def member_vote_summary_api(request):
    member_name = request.GET.get('member_name')
    if not member_name:
        return JsonResponse({'error': 'member_name parameter is required'}, status=400)

    summaries = VoteSummary.objects.filter(member_name=member_name)
    if not summaries.exists():
        return JsonResponse({'error': 'No summary data available. Please generate it first.'}, status=404)

    max_clusters = {}

    for vote_type in ['찬성', '반대', '기권', '불참']:
        top_summary = summaries.order_by(f'-{vote_type}').first()
        if not top_summary:
            continue

        bill_count = top_summary.bill_count if top_summary.bill_count > 0 else 1

        counts = {
            '찬성': top_summary.찬성,
            '반대': top_summary.반대,
            '기권': top_summary.기권,
            '불참': top_summary.불참,
        }
        ratios = {k: round(counts[k] / bill_count * 100, 2) for k in counts}

        # 클러스터 키워드를 Bill 테이블에서 가져오기
        bill = Bill.objects.filter(cluster=top_summary.cluster).first()
        cluster_keyword = bill.cluster_keyword if bill and bill.cluster_keyword else "알 수 없음"

        max_clusters[vote_type] = {
            
            'cluster_keyword': cluster_keyword,
            'cluster_id': bill.cluster if bill else None,
            'counts': counts,
            'ratios': ratios,
            'bill_count': bill_count,
        }

    return JsonResponse(max_clusters)
























