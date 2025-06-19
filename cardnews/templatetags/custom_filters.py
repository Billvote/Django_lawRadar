# cardnews/templatetags/custom_filters.py
# -*- coding: utf-8 -*-
from django import template

register = template.Library()


@register.filter(name="dict_get") 
def dict_get(dictionary, key):
    """
    Django 템플릿에서 dict 값을 안전하게 꺼내는 필터.

        {{ my_dict|dict_get:"some_key" }}

    key가 없으면 빈 문자열을 반환합니다.
    """
    # dictionary 가 dict 타입일 때
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")

    # QueryDict 등 다른 매핑 타입도 고려
    try:
        return dictionary.get(key, "")
    except Exception:
        return ""
