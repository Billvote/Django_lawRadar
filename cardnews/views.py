from django.shortcuts import render

# Create your views here.

def cardnews_home(request):
    return render(request, 'cardnews_home.html')