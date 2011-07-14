from django.conf import settings
from django.conf.urls.defaults import url, patterns
from django.views.generic import list

from newsy.models import NewsItem


urlpatterns = patterns('newsy.views',
    url(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<slug>[\-\d\w]+)/$',
        'item_view', name='published-item-view'),
    url(r'^upcoming/(?P<slug>[\-\d\w]+)/$','unpublished_item_view',
        name='unpublished-item-view'),
)

urlpatterns += patterns('',
    url(r'^$',list.ListView.as_view(queryset=NewsItem.objects.filter(published=True),
                                    paginate_by=25), name='published-items'),
    url(r'^upcoming/$', list.ListView.as_view(queryset=NewsItem.objects.filter(published=False).order_by('title')),
        name='unpublished-items'),
)
