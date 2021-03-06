from django.conf import settings
from django.conf.urls.defaults import url, patterns

from newsy.models import NewsItem
from newsy.feeds import RssNewsItemFeed



urlpatterns = patterns('newsy.views',
    url(r'^$', 'item_list', name='newsy-items'),
    url(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<slug>[\-\d\w]+)/$',
        'item_view', name='published-item-view'),
    url(r'^(?P<year>\d{4})/((?P<month>\d{1,2})/((?P<day>\d{1,2})/)?)?$',
        'item_list', name='archive-view'),
    url(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/$',
        'item_list', name='month-view'),
    url(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/$',
        'item_list', name='date-view'),
    url(r'^upcoming/$', 'upcoming_item_list', name='upcoming-newsy-items'),
    url(r'^upcoming/(?P<slug>[\-\d\w]+)/$','unpublished_item_view',
        name='unpublished-item-view'),
    url(r'^tag/$', 'tags_view', name='tags-view'),
    url(r'^tag/(?P<tag>[\d\w\- &]{1,64})/$', 'item_list', name='tag-view'),
    url(r'^rss/', RssNewsItemFeed(), name='newsy-rss-feed'),
    url(r'^tag/(?P<tag>[\d\w\- &]{1,64})/rss/$', RssNewsItemFeed(),
        name='newsy-rss-tag-feed'),
)
