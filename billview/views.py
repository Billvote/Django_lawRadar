from django.shortcuts import render

# Create your views here.

from django.shortcuts import render

def bill_main(request):
    return render(request, 'bill_main.html')