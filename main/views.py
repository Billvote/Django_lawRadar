from django.db.models import (
    Q, Count, Max, Subquery, OuterRef, F, Value, DateField
)
from django.core.paginator import Paginator
from collections import defaultdict, Counter
from django.shortcuts import render, redirect
from django.urls import reverse
from billview.models import Bill
from geovote.models import Vote
from .models import VoteSummary
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core.cache import cache
from django.db.models.functions import Random, Coalesce
import logging, random, re

logger = logging.getLogger(__name__)

# ───────────────────────── 1. 자동완성 엔드포인트 ─────────────────────────
@require_GET
def autocomplete(request):
    """
    GET /api/autocomplete/?term=<검색어>
    - 2글자 이상 입력 시 제목·키워드에서 최대 10건 반환
    """
    term = request.GET.get("term", "").strip()
    if len(term) < 2:
        return JsonResponse([], safe=False)

    cache_key = f"ac:{term.lower()}"
    if (cached := cache.get(cache_key)):
        return JsonResponse(cached, safe=False)

    # ① 제목 후보
    titles = (
        Bill.objects
            .filter(title__icontains=term)
            .values_list("title", flat=True)[:5]
    )

    # ② 키워드 후보
    kw_rows = (
        Bill.objects
            .filter(cluster_keyword__icontains=term)
            .values_list("cluster_keyword", flat=True)[:50]
    )
    kw_set = set()
    for row in kw_rows:
        for k in (row or "").split(","):
            k = k.strip()
            if term.lower() in k.lower():
                kw_set.add(k)
            if len(kw_set) >= 10:
                break
        if len(kw_set) >= 10:
            break

    suggestions = list(dict.fromkeys(list(titles) + list(kw_set)))[:10]
    cache.set(cache_key, suggestions, 600)
    return JsonResponse(suggestions, safe=False)

# ───────────────────────── 2. 클러스터 키워드(노드) JSON ─────────────────────────
def cluster_keywords_json(request):
    cached = cache.get('cluster_keywords_data')
    if cached:
        return JsonResponse(cached, safe=False)

    qs = (
        Bill.objects
            .exclude(cluster_keyword__isnull=True)
            .exclude(cluster_keyword__exact='')
            .values('cluster', 'cluster_keyword')
            .annotate(
                num_bills=Count('id', distinct=True),
                latest_passed_date=Max('vote__date')
            )
            .filter(num_bills__gt=1)
            .order_by(Random())
    )
    qs_list = list(qs[:300])

    sample_size = 100
    sampled_qs = random.sample(qs_list, min(len(qs_list), sample_size))

    result = [{
        'cluster_index'     : row['cluster'],
        'keyword'           : row['cluster_keyword'],
        'num_bills'         : row['num_bills'],
        'latest_passed_date': (
            row['latest_passed_date'].isoformat()
            if row['latest_passed_date'] else None
        ),
        'url'               : f"/cardnews/cluster/{row['cluster']}/",
    } for row in sampled_qs]

    cache.set('cluster_keywords_data', result, 600)
    return JsonResponse(result, safe=False)

# ───────────────────────── 3. 홈(갤럭시) 뷰 ─────────────────────────
def cluster_galaxy_view(request):
    return render(request, 'home.html')

def home(request):
    clusters = (
        Bill.objects.filter(cluster__isnull=False, cluster__gt=0)
        .values('cluster', 'cluster_keyword').distinct().order_by('cluster')
    )
    clusters = [{
        'cluster': c['cluster'],
        'keyword': c['cluster_keyword'] or '키워드 없음'
    } for c in clusters if isinstance(c['cluster'], int) and c['cluster'] > 0]

    return render(request, 'home.html', {'clusters': clusters})

def aboutUs(request):
    return render(request, 'aboutUs.html')

# ───────────────────────── 4. 검색 뷰 ─────────────────────────
def search(request):
    query  = request.GET.get('q', '').strip()
    page_obj = page_range = None
    cluster_keywords_dict = {}
    top_clusters = []
    cluster_color_map = {}
    total_results_count = 0

    if query:
        matching_bills = Bill.objects.filter(
            Q(title__icontains=query) |
            Q(cleaned__icontains=query) |
            Q(summary__icontains=query) |
            Q(cluster_keyword__icontains=query)
        )

        label_counts = {
            item['label']: item['count']
            for item in matching_bills.exclude(label__isnull=True)
                     .values('label').annotate(count=Count('id'))
        }

        cluster_to_keywords = defaultdict(set)
        for bill in matching_bills:
            if bill.cluster_keyword and bill.cluster is not None:
                for kw in bill.cluster_keyword.split(','):
                    kw = kw.strip()
                    if kw:
                        cluster_to_keywords[bill.cluster].add(kw)

        cluster_keywords_dict = {
            cid: ", ".join(sorted(kws))
            for cid, kws in cluster_to_keywords.items()
        }

        results = (
            Bill.objects.filter(
                Q(title__icontains=query) |
                Q(summary__icontains=query) |
                Q(cluster_keyword__icontains=query),
                id__in=Subquery(
                    Bill.objects.filter(label=OuterRef('label'))
                        .order_by('-bill_number')
                        .values('id')[:1]
                )
            )
            .annotate(last_vote_date=Max('vote__date'))
            .order_by('-bill_number')
        )
        total_results_count = results.count()

        cluster_counter = Counter(bill.cluster for bill in results if bill.cluster)

        palette = [
            '#bef264', '#67e8f9', '#f9a8d4', '#fde68a', '#fdba74',
            '#6ee7b7', '#c3b4fc', '#fda4af', '#5eead4', '#34d399',
            '#f472b6', '#facc15', '#fb7185', '#818cf8', '#38bdf8',
        ]
        random.shuffle(palette)
        cluster_ids = {bill.cluster for bill in results if bill.cluster}
        cluster_color_map = {
            cid: palette[i % len(palette)] for i, cid in enumerate(cluster_ids)
        }

        for i, (cid, _) in enumerate(cluster_counter.most_common(2)):
            kw_str = cluster_keywords_dict.get(cid)
            if kw_str:
                top_clusters.append({
                    'cluster_id': cid,
                    'keywords'  : [k.strip() for k in kw_str.split(',') if k.strip()],
                    'color'     : palette[i % len(palette)],
                })

        for bill in results:
            bill.label_count = label_counts.get(bill.label, '-')
            words = bill.title.split()
            bill.title_custom = (
                " ".join(words[:5]) + "<br>" + " ".join(words[5:])
            ) if len(words) > 4 else bill.title

        results = sorted(results,
                         key=lambda b: label_counts.get(b.label, 0),
                         reverse=True)

        paginator = Paginator(results, 10)
        page_obj  = paginator.get_page(request.GET.get('page'))
        current   = page_obj.number
        total     = paginator.num_pages
        start     = ((current - 1) // 10) * 10 + 1
        end       = min(start + 9, total)
        page_range = range(start, end + 1)

    context = {
        'query'                : query,
        'page_obj'             : page_obj,
        'page_range'           : page_range,
        'total_results_count'  : total_results_count,
        'cluster_keywords_dict': cluster_keywords_dict,
        'top_clusters'         : top_clusters,
        'cluster_color_map'    : cluster_color_map,
    }
    return render(request, 'search.html', context)

# ───────────────────────── 5. 해시태그 리다이렉트 ─────────────────────────
def cluster_index(request, cluster_number: int):
    return redirect(
        f"{reverse('history:history_list')}?cluster={cluster_number}"
    )

# ───────────────────────── 6. 의원별 표결 통계 저장 ─────────────────────────
def calculate_votesummary(member_name):
    votes = (
        Vote.objects.filter(member__name=member_name)
        .values('bill__cluster', 'result')
        .annotate(count=Count('id'))
    )
    clusters = {
        v['bill__cluster'] for v in votes if v['bill__cluster'] is not None
    }

    cluster_keywords = {}
    for b in (
        Bill.objects.filter(cluster__in=clusters)
            .exclude(cluster_keyword__isnull=True)
            .exclude(cluster_keyword__exact='')
            .values('cluster', 'cluster_keyword')
    ):
        cid, kw = b['cluster'], b['cluster_keyword']
        if cid not in cluster_keywords and not kw.isdigit():
            cluster_keywords[cid] = kw
    for cid in clusters:
        cluster_keywords.setdefault(cid, "알 수 없음")

    cluster_bill_counts = {
        cid: Bill.objects.filter(cluster=cid).count() for cid in clusters
    }

    summary = {
        cid: {'찬성': 0, '반대': 0, '기권': 0, '불참': 0}
        for cid in clusters
    }
    for v in votes:
        cid = v['bill__cluster']
        result = v['result'] if v['result'] in summary[cid] else '기권'
        summary[cid][result] += v['count']

    VoteSummary.objects.filter(member_name=member_name).delete()
    for cid in clusters:
        s = summary[cid]
        VoteSummary.objects.create(
            member_name    = member_name,
            cluster        = cid,
            cluster_keyword= cluster_keywords[cid],
            bill_count     = cluster_bill_counts.get(cid, 1),
            찬성            = s['찬성'],
            반대            = s['반대'],
            기권            = s['기권'],
            불참            = s['불참'],
        )
