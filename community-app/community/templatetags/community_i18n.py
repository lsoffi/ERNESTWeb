from django import template
from community.i18n import tr
register = template.Library()
register.simple_tag(tr, name='tr')
