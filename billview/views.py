from django.shortcuts import render
from django.db.models import Count, Q
from .models import Bill
from geovote.models import Vote
from django.shortcuts import render
from django.core.paginator import Paginator

def detail_bill(request, id):
    bill = Bill.objects.get(id=id)
    vote = Vote.objects.filter(bill=bill).select_related('member')
    party_stats = Vote.objects.filter(bill=bill).values('member__party').annotate(
        agree=Count('id', filter=Q(vote_result='찬성')),
        oppose=Count('id', filter=Q(vote_result='반대')),
        abstain=Count('id', filter=Q(vote_result='기권')),
    )
    context = {
        'bill': bill,
        'vote': vote,
        'party_stats': party_stats
    }
    return render(request, 'detail.html', context)

def index_bill(request):
    bills = Bill.objects.all()
    paginator = Paginator(bills, 10)  # 페이지당 10개
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    current_page = page_obj.number # 현재 페이지 번호
    total_pages = paginator.num_pages # 총 페이지
    max_page_buttons = 10 # 한번에 보여줄 최대 수

    # 현재 페이지 번호가 속한 10페이지 그룹을 구함
    group = (current_page - 1) // max_page_buttons
    
    start_page = group * max_page_buttons + 1
    end_page = min(start_page + max_page_buttons - 1, total_pages)
    
    page_range = range(start_page, end_page + 1)

    context = {
        'page_obj': page_obj,
        'page_range': page_range
    }
    return render(request, 'index.html', context)