from datetime import date, timedelta
from urllib import unquote

from django.contrib.auth.decorators import permission_required
from django.http import Http404, HttpResponseServerError
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.views.generic.list import ListView

from cms.utils import get_language_from_request

from tagging.models import TaggedItem

from newsy.models import NewsItem



class NewsListView(ListView):
    queryset = NewsItem.site_objects
    published = True
    
    def get_queryset(self):
        qs = super(NewsListView, self).get_queryset()
        
        tags = getattr(self, 'tags', [])
        kwargs = getattr(self, 'kwargs', {})
        if 'tag' in kwargs:
            print 'tag: %s' % (kwargs['tag'])
            tags.append(unquote(kwargs['tag']))
        
        if getattr(self, 'published', True):
            qs = qs.filter(published=True)
        else:
            qs = qs.filter(published=False)
        
        if tags:
            qs = TaggedItem.objects.get_by_model(qs, tags)
        
        if kwargs.get('year', None):
            qs = qs.filter(publication_date__year=kwargs['year'])
        if kwargs.get('month', None):
            qs = qs.filter(publication_date__month=kwargs['month'])
        if kwargs.get('day', None):
            qs = qs.filter(publication_date__day=kwargs['day'])
        
        return qs

item_list = NewsListView.as_view()
upcoming_item_list = permission_required('newsy.change_newsitem')(NewsListView.as_view(published=False))

def item_view(request, year, month, day, slug):
    try:
        page = NewsItem.objects.get(publication_date__year=year,
                                    publication_date__month=month,
                                    publication_date__day=day,
                                    slug=slug)
    except NewsItem.DoesNotExist, NewsItem.MultipleObjectsReturned:
        raise Http404()
    
    context = RequestContext(request)
    context['lang'] = get_language_from_request(request)
    context['current_page'] = page
    context['has_change_permissions'] = page.has_change_permission(request)
    return render_to_response(page.template, context)

@permission_required('newsy.change_newsitem')
def unpublished_item_view(request, slug):
    try:
        page = NewsItem.objects.get(published=False, slug=slug)
    except NewsItem.DoesNotExist:
        raise Http404()
    except NewsItem.MultipleObjectsReturned:
        raise HttpResponseServerError(u'Multiple unpublished items found with '
                                      'the slug: %s' % (slug,))
    
    if not page.has_change_permission(request):
        raise Http404()
    #request._current_page_cache = page
    context = RequestContext(request)
    context['lang'] = get_language_from_request(request)
    context['current_page'] = page
    context['has_change_permissions'] = page.has_change_permission(request)
    return render_to_response(page.template, context)

def archive_view(request, year, month=None, day=None, **kwargs):
    kwargs.setdefault('filters', {})
    kwargs['filters']['publication_date__year'] = year
    
    if day:
        kwargs['filters']['publication_date__day'] = day
    if month:
        kwargs['filters']['publication_date__month'] = month
    
    return item_list(request, **kwargs)
