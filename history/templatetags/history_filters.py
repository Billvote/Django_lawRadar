from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def split_by_comma(value):
    if isinstance(value, str) and value:
        return [item.strip() for item in value.split(',') if item.strip()]
    return []

@register.filter
def dict_get(d, key):
    return d.get(key, '')