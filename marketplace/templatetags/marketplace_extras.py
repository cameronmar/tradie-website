from django import template

register = template.Library()


@register.filter
def getitem(obj, key):
    try:
        return obj[key]
    except (KeyError, TypeError):
        return None
