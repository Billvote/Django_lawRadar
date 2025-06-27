# cardnews/templatetags/custom_filters.py
# -*- coding: utf-8 -*-
from django import template
import random

register = template.Library()
PALETTE = [
    '#bef264', '#67e8f9', '#f9a8d4', '#fde68a', '#fdba74',
    '#6ee7b7', '#c3b4fc', '#fda4af', '#5eead4', '#34d399',
    '#f472b6', '#facc15', '#fb7185', '#818cf8', '#38bdf8',
    '#34d399', '#f9a8d4', '#93c5fd', '#fdba74', '#c3b4fc',
    '#bef264', '#fdbaaa', '#38bdf8', '#fcd34d', '#a5b4fc',
    '#6ee7b7', '#fca5a5', '#67e8f9', '#fb7185', '#bbf7d0',
    '#fde68a', '#818cf8', '#fda4af', '#86efac', '#facc15',
    '#5eead4', '#f472b6', '#fbbf24'
    ]

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


@register.simple_tag
def random_color_for_cluster(cluster):
    random.seed(cluster)  # 키워드마다 같은 색이 나오도록 시드 고정
    return random.choice(PALETTE)

@register.filter
def split_by_comma(value):
    if isinstance(value, str) and value:
        return [item.strip() for item in value.split(',') if item.strip()]
    return []