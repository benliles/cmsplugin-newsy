from datetime import date

from django.contrib.sites.models import Site
from django.contrib.syndication.views import Feed
from django.core.urlresolvers import reverse

from tagging.models import TaggedItem, Tag

from newsy.models import NewsItem


_current_site = Site.objects.get_current

class RssNewsItemFeed(Feed):
    def title(self, obj=None):
        if not obj:
            return u'Latest news for %s' % (_current_site().name,)
        else:
            return u'Latest news for %s at %s' % (str(obj),
                                                  _current_site().name,)
    
    def link(self, obj=None):
        if not obj:
            return reverse('newsy-rss-feed')
        else:
            return reverse('newsy-rss-tag-feed', kwargs={'tag': str(obj)})
    
    def description(self, obj=None):
        return self.title(obj)
    
    def feed_copyright(self):
        return u'Copyright (c) %d, %s' % (date.today().year,
                                          _current_site().name,)
    
    def get_object(self, request, *args, **kwargs):
        return kwargs.get('tag', None)
    
    def categories(self, obj):
        if obj:
            return [str(obj)]
        return []
    
    def items(self, obj):
        qs = NewsItem.site_objects.filter(published=True)
        
        if obj:
            return TaggedItem.objects.get_by_model(qs, [obj])[:5]
        return qs[:5]
    
    def item_title(self, item):
        return item.title
    
    def item_description(self, item):
        return item.description
    
    def item_link(self, item):
        return item.get_absolute_url()
    
    def item_pubdate(self, item):
        return item.publication_date
    
    def item_categories(self, item):
        return map(lambda t: t.name,
                   Tag.objects.get_for_object(item))
