from datetime import date, timedelta

from django.contrib.auth.decorators import permission_required
from django.http import Http404, HttpResponseServerError, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.views.generic.list import ListView

from cms.utils import get_language_from_request

from tagging.models import TaggedItem, Tag

from newsy.models import NewsItem



class NewsListView(ListView):
    queryset = NewsItem.site_objects
    published = True
    
    def get_tags(self):
        tags = getattr(self, 'tags', [])
        kwargs = getattr(self, 'kwargs', {})
        if 'tag' in kwargs:
            tags.append(kwargs['tag'])
        
        return tags
    
    def get_date_filters(self):
        filters = {}
        kwargs = getattr(self, 'kwargs', {})
        if kwargs.get('year', None):
            filters['publication_date__year'] = kwargs['year']
        if kwargs.get('month', None):
            filters['publication_date__month'] = kwargs['month']
        if kwargs.get('day', None):
            filters['publication_date__day'] = kwargs['day']
        return filters
    
    def get_queryset(self):
        qs = super(NewsListView, self).get_queryset()
        kwargs = getattr(self, 'kwargs', {})
        
        if getattr(self, 'published', True):
            qs = qs.filter(published=True)
        else:
            qs = qs.filter(published=False)
        
        tags = self.get_tags()
        date_filters = self.get_date_filters()
        
        if tags:
            qs = TaggedItem.objects.get_by_model(qs, tags)
        
        if date_filters:
            qs = qs.filter(**date_filters)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super(NewsListView, self).get_context_data(**kwargs)
        tags = self.get_tags()
        if tags:
            context['news_tags'] = tags
        context['news_year'] = getattr(self, 'kwargs', {}).get('year', None)
        context['news_month'] = getattr(self, 'kwargs', {}).get('month', None)
        context['news_day'] = getattr(self, 'kwargs', {}).get('day', None)

        return context

item_list = NewsListView.as_view(paginate_by=15)
upcoming_item_list = permission_required('newsy.change_newsitem')(
    NewsListView.as_view(published=False, paginate_by=15))

def item_view(request, year, month, day, slug):
    try:
        page = NewsItem.objects.get(publication_date__year=year,
                                    publication_date__month=month,
                                    publication_date__day=day,
                                    slug=slug)
    except NewsItem.MultipleObjectsReturned:
        raise Http404()
    except NewsItem.DoesNotExist:
        try:
            page = NewsItem.objects.get(slug=slug)
            return HttpResponseRedirect(page.get_absolute_url())
        except NewsItem.DoesNotExist, NewItem.MultipleObjectsReturned:
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

class TagsView(ListView):
    template_name = 'newsy/tag_list.html'

    def get_queryset(self, *args, **kwargs):
        return Tag.objects.usage_for_queryset(
                NewsItem.site_objects.filter(published=True),
                counts=True)

tags_view = TagsView.as_view()

