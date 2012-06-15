import re

from django.core.urlresolvers import reverse

from menus.base import NavigationNode, Modifier
from menus.menu_pool import menu_pool
from django.utils.translation import ugettext_lazy as _
from cms.menu_bases import CMSAttachMenu

from tagging.models import Tag

from newsy.models import NewsItem



class NewsyMenu(CMSAttachMenu):
    name = _('News Menu')

    def get_nodes(self, request):
        qs = NewsItem.site_objects.filter(published=True)
        nodes = []
        nodes.append(NavigationNode(_('Tags'), reverse('tags-view'), 'tags'))

        tags = Tag.objects.usage_for_queryset(qs, counts=True)
        tags.sort(key=lambda t:t.count, reverse=True)
        for tag in tags:
            nodes.append(NavigationNode(_(tag.name), reverse('tag-view',
                kwargs={'tag':tag.name}), 'tag_%s' % (tag.name,), 'tags'))

        for year in qs.dates('publication_date', 'year', order='DESC'):
            nodes.append(NavigationNode(year.year, reverse('archive-view', 
                kwargs={'year': year.year}), year.strftime('year_%Y')))
            for month in qs.filter(publication_date__year=year.year).dates('publication_date',
                            'month', order='ASC'):
                nodes.append(NavigationNode(month.strftime('%B'),
                        reverse('month-view', kwargs={'year': month.year,
                            'month': month.month}),
                            month.strftime('year_%Y_month_%m'),
                            month.strftime('year_%Y')))

                for day in qs.filter(publication_date__year=month.year,
                        publication_date__month=month.month).dates('publication_date',
                                'day', order='ASC'):
                    nodes.append(NavigationNode(day.day, reverse('date-view',
                        kwargs={'year': day.year, 'month': day.month, 'day':
                            day.day}), day.strftime('year_%Y_month_%m_day_%d'),
                        day.strftime('year_%Y_month_%m')))

        for news_item in qs:
            pub = news_item.publication_date
            nodes.append(NavigationNode(news_item.get_short_title(),
                    reverse('published-item-view', kwargs={'year': pub.year,
                        'month': pub.month, 'day': pub.day, 'slug':
                        news_item.slug}), 'news_item_%d' % (news_item.pk,), 
                    pub.strftime('year_%Y_month_%m_day_%d')))

        return nodes

menu_pool.register_menu(NewsyMenu)

class NewsCleaner(Modifier):
    def modify(self, request, nodes, namespace, root_id, post_cut, breadcrumb):
        if post_cut or breadcrumb:
            return nodes

        tags = 0

        filter_dates = re.compile(r'^year_\d{4}_month_\d{1,2}(_day_\d{1,2})?$')

        for node in nodes:
            if node.namespace != 'NewsyMenu':
                continue
            if node.parent_id == 'tags':
                tags += 1
                if tags > 5:
                    node.visible = False
                continue
            if filter_dates.match(str(node.parent_id)):
                node.visible = False

        return nodes

menu_pool.register_modifier(NewsCleaner)

