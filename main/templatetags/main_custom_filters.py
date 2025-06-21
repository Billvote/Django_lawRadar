from django import template

register = template.Library()

@register.filter
def split_by_comma(value):
    if isinstance(value, str) and value:
        return [item.strip() for item in value.split(',') if item.strip()]
    return []

@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''