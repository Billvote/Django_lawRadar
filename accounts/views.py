from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm

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