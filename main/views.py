from django.shortcuts import render
from django.db.models import Q
from billview.models import Bill
from geovote.models import Vote

def home(request):
    return render(request, 'home.html')

def aboutUs(request):
    return render(request, 'aboutUs.html')

def search(request):
    # 검색어 없을 시 처리
    query = request.GET.get('q', '')
    results = []

    if query:
        results = Bill.objects.filter(
            Q(title__icontains=query) |
            Q(summary__icontains=query) |
            Q(cluster_keyword__icontains=query)
        )
    
    context = {
        'query': query,
        'results': results,
    }

    return render(request, 'search.html', context)