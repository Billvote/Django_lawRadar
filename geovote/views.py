from django.shortcuts import render

# Create your views here.
def geovote_main(request):
    return render(request, 'geovote_main.html')

def map_view(request):
    return render(request, 'map.html')
