from django.shortcuts import render

def get_data_for_congress(congress_num):
    # 예시: congress_number에 따라 데이터 조회 & 가공 로직 작성
    # 아래는 임시 데이터 예시
    if congress_num == 20:
        return {"chart_data": [10, 20, 30]}
    elif congress_num == 21:
        return {"chart_data": [15, 25, 35]}
    elif congress_num == 22:
        return {"chart_data": [20, 30, 40]}
    else:
        return {"chart_data": []}

def dashboard(request, congress_num):
    if congress_num not in [20, 21, 22]: # 유효하지 않은 링크 처리
        raise Http404("Invalid congress num")

    data = get_data_for_congress(congress_num)

    context = {
        'congress_num': congress_num,
        'data': data,
    }

    return render(request, 'dashboard.html', context)