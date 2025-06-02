from django.shortcuts import render

def detail_history(request, id):
    bill = Bill.objects.get(id=id)
    return render(request, 'history_detail.html', context)