from django.utils.translation import ugettext as _
from django.template.loader import select_template

from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from tagging.models import TaggedItem, Tag

from newsy.models import LatestNewsPlugin, NewsItem



class CMSLatestNewsPlugin(CMSPluginBase):
    model = LatestNewsPlugin
    name = _("Latest News Items")
    render_template = "cms/plugins/newsy/latest.html"
    
    def render(self, context, instance, placeholder):
        context.update({
            'object': instance})
        return context

plugin_pool.register_plugin(CMSLatestNewsPlugin)
