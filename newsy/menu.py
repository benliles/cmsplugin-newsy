from django.core.urlresolvers import reverse

from menus.base import NavigationNode
from menus.menu_pool import menu_pool
from django.utils.translation import ugettext_lazy as _
from cms.menu_bases import CMSAttachMenu



class NewsyMenu(CMSAttachMenu):
    name = _('News Menu')

    def get_nodes(self, request):
        nodes = []
        news = NavigationNode(_('News'), reverse('newsy-items'), 'news')
        nodes.append(news)



        return nodes

menu_pool.register_menu(NewsyMenu)

