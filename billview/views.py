from django.shortcuts import render
from django.db.models import Count, Q
from .models import Bill
from geovote.models import Vote
from django.shortcuts import render

def index_bill(request):
    bills = Bill.objects.all()
    context = {
        'bills' = bills
    }
    return render(request, 'index.html')

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

def index(request):
    return render(request, 'index.html', context)