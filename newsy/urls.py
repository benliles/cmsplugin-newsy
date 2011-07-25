from django.conf import settings
from django.conf.urls.defaults import url, patterns
from django.views.generic import list

from newsy.models import NewsItem



urlpatterns = patterns('newsy.views',
    url(r'^$', 'item_list', name='newsy-items'),
    url(r'^upcoming/$', 'upcoming_item_list', name='upcoming-newsy-items'),
    url(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<slug>[\-\d\w]+)/$',
        'item_view', name='published-item-view'),
    url(r'^(?P<year>\d{4})/((?P<month>\d{1,2})/((?P<day>\d{1,2})/)?)?$',
        'archive_view', name='archive-view'),
    url(r'^upcoming/(?P<slug>[\-\d\w]+)/$','unpublished_item_view',
        name='unpublished-item-view'),
)
