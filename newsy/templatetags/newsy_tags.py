from django import template

from cms.templatetags.cms_tags import Placeholder

from newsy.placeholders import render_newsy_placeholder



register = template.Library()

def _get_placeholder(page, name):
    if not hasattr(page, '_tmp_placeholders_cache'):
        cache = {}
        
        for placeholder in page.placeholders.all():
            cache[placeholder.slot] = placeholder
        
        page._tmp_placeholders_cache = cache
    
    return page._tmp_placeholders_cache.get(name, None)

class NewsyPlaceholder(Placeholder):
    name='newsy_placeholder'
    
    def render_tag(self, context, name, extra_bits, nodelist=None):
        width = None
        inherit = False
        for bit in extra_bits:
            if bit == 'inherit':
                inherit = True
            elif bit.isdigit():
                width = int(bit)
                import warnings
                warnings.warn(
                    "The width parameter for the placeholder tag is deprecated.",
                    DeprecationWarning
                )
        
        if not 'current_page' in context:
            return ''
        
        if width:
            context.update({'width': width})
        
        placeholder = _get_placeholder(context['current_page'], name)
        
        if placeholder:
            content = render_newsy_placeholder(placeholder, context, name)
        else:
            content = None
        
        if not content and nodelist:
            return nodelist.render(context)
        return content

register.tag(NewsyPlaceholder)