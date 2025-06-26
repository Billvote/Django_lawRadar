from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from accounts.models import BillLike
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from collections import Counter, defaultdict
from django.db.models import Q
from billview.models import Bill



def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save() # user 생성 및 저장
            return redirect('accounts:login') # 로그인 페이지로 이동
    else:
        form = CustomUserCreationForm()
    context = {'form': form}
    return render(request, 'signup.html', context)

def login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, request.POST)  # request 꼭 넣기
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)  # Django의 login 함수로 세션 발급
            return redirect('home')  # 로그인 성공 시 이동할 곳
    else:
        form = CustomAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout(request):
    auth_logout(request)
    return redirect('home')

# my_page 화면
@login_required
def my_page(request):
    # 좋아요 버튼
    liked_bills = BillLike.objects.filter(user=request.user).select_related('bill')
    liked_ids = liked_bills.values_list('bill_id', flat=True)
    bill_list = [like.bill for like in liked_bills]

    # 1) 관심 법안의 클러스터
    cluster_ids = [bill.cluster for bill in bill_list if bill.cluster]
    cluster_counts = Counter(cluster_ids)
    cluster_counts = dict(cluster_counts)


    # 2) 클러스터별 키워드 모으기 (중복 제거)
    cluster_keywords = defaultdict(set)
    for bill in bill_list:
        if bill.cluster is not None and bill.cluster_keyword:
            # 만약 키워드가 콤마 구분이면 분리해서 저장 가능
            keywords = [kw.strip() for kw in bill.cluster_keyword.split(',')]
            for kw in keywords:
                cluster_keywords[bill.cluster].add(kw)
            # 지금은 그냥 통째로 저장
            # cluster_keywords[bill.cluster].add(bill.cluster_keyword.strip())

    # 3) 집합을 콤마로 연결한 문자열로 변환
    for cluster, keywords in cluster_keywords.items():
        cluster_keywords[cluster] = ", ".join(sorted(keywords))

    # 3) 추천할 법안: 내가 좋아요한 클러스터를 포함하거나 키워드가 유사한 법안 추천
    # 예를 들어, 같은 클러스터 법안 중 좋아요 안 한 것 추천
    # recommended_bills = Bill.objects.filter(
    #     Q(cluster__in=cluster_counts.keys()) |
    #     Q(cluster_keyword__in=cluster_keywords.values())
    # ).exclude(id__in=liked_ids).distinct()[:5]

     # 페이지네이션
    paginator = Paginator(bill_list, 5)
    page_obj = paginator.get_page(request.GET.get("page"))
    current = page_obj.number
    total = paginator.num_pages
    start = ((current - 1) // 10) * 10 + 1
    end = min(start + 9, total)
    page_range = range(start, end + 1)

    context = {
        'liked_bills': page_obj,
        'liked_ids': list(liked_ids),

        'page_obj': page_obj,
        'page_range': page_range,

        # 클러스터
        'cluster_counts': cluster_counts,
        'cluster_keywords': cluster_keywords, 
    }
    return render(request, 'my_page.html', context)