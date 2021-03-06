from datetime import date
from logging import getLogger

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.managers import CurrentSiteManager
from django.db import models
from django.template.loader import select_template
from django.utils.translation import ugettext_lazy as _

from cms.models import Placeholder, Page, CMSPlugin

from photologue.models import ImageModel

from tagging.fields import TagField as BaseTagField
from tagging.models import TaggedItem, Tag



log = getLogger('newsy.models')

try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ["^newsy\.models\.TagField"])
except ImportError:
    pass

class TagField(BaseTagField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 4096)
        super(TagField, self).__init__(*args, **kwargs)

    def get_internal_type(self):
        return 'TextField'

class NewsItemThumbnail(ImageModel):
    news_item = models.OneToOneField('NewsItem',related_name='thumbnail',
                                  on_delete=models.CASCADE)
    
    def __unicode__(self):
        return u'%s thumbnail' % (self.news_item.title,)
    
    class Meta:
        db_table = 'newsy_newsitem_thumbnail'

class NewsItem(models.Model):
    title = models.CharField(_('title'), max_length = 255)
    short_title = models.CharField(_('short title'), max_length = 255, blank = True,
                                   null = True, help_text = _('Provide an optional shorter alternative title'))
    page_title = models.CharField(_('page title'), max_length = 255, blank = True,
                                  null = True, help_text = _('Provide an optional '
                                  'html page title override'))
    template_choices = [(x, _(y)) for x,y in settings.NEWSY_TEMPLATES]
    template = models.CharField(_("template"), max_length=255, choices=template_choices, help_text=_('The template used to render the content.'))
    slug = models.SlugField(_("slug"), max_length=255, db_index=True)
    description = models.TextField(_('description'), blank=True, null=True, help_text=_('A short description of the news item'))
    publication_date = models.DateTimeField(_('publication date'), blank=True, null=True, db_index=True, help_text=_('Publication date and time of the news item'))
    published = models.BooleanField(_('published'), default=False, db_index=True)
    sites = models.ManyToManyField(Site)
    placeholders = models.ManyToManyField(Placeholder, editable=False)
    tags = TagField()
    
    moderator_state = 0
    
    objects = models.Manager()
    site_objects = CurrentSiteManager('sites')
    
    class Meta:
        get_latest_by = 'publication_date'
        ordering = ['-publication_date','title']
    
    def __unicode__(self):
        return self.title
    
    @models.permalink
    def get_absolute_url(self, *args, **kwargs):
        if self.published:
            return ('published-item-view',(),{'year':self.publication_date.year,
                                              'month': self.publication_date.month,
                                              'day': self.publication_date.day,
                                              'slug': self.slug})
        return ('unpublished-item-view', (), {'slug': self.slug})
    
    def get_page_title(self, language=None, fallback=True, version_id=None, force_reload=False):
        if self.page_title:
            return self.page_title
        return self.title
    
    def get_short_title(self):
        if self.short_title:
            return self.short_title
        return self.title
    
    def get_publication_month(self):
        if self.publication_date:
            return date(self.publication_date.year,
                        self.publication_date.month, 1)
        else:
            return date.today().replace(day=1)
    
    def get_related(self, max=5):
        return TaggedItem.objects.get_related(self,
                   NewsItem.site_objects.filter(published=True),
                   num=max)
    
    def get_next_published(self):
        if not self.publication_date or not self.published:
            return None
        
        try:
            return NewsItem.site_objects.filter(
                published=True,
                publication_date__gt=self.publication_date).order_by(
                    'publication_date')[0]
        except:
            return None
    
    def get_previous_published(self):
        if not self.publication_date or not self.published:
            return None
        
        try:
            return NewsItem.site_objects.filter(
                published=True,
                publication_date__lt=self.publication_date).order_by(
                    '-publication_date')[0]
        except:
            return None
    
    def get_cached_ancestors(self, ascending=True):
        return []
    
    def get_template(self):
        """
        get the template of this page if defined or if closer parent if
        defined or DEFAULT_PAGE_TEMPLATE otherwise
        """
        template = None
        if self.template and len(self.template)>0:
            template = self.template
        else:
            template = settings.NEWSY_TEMPLATES[0][0]
        return template
    
    def rescan_placeholders(self):
        """
        Rescan and if necessary create placeholders in the current template.
        """
        # inline import to prevent circular imports
        log.debug('NewsItem.rescan_placeholders(%s)' % (unicode(self),))
        from cms.utils.plugins import get_placeholders
        placeholders = get_placeholders(self.get_template())
        found = {}
        for placeholder in self.placeholders.all():
            if placeholder.slot in placeholders:
                found[placeholder.slot] = placeholder
        for placeholder_name in placeholders:
            if not placeholder_name in found:
                placeholder = Placeholder.objects.create(slot=placeholder_name)
                self.placeholders.add(placeholder)
                found[placeholder_name] = placeholder
    
    def has_change_permission(self, request):
        opts = self._meta
        if request.user.is_superuser:
            return True
        return request.user.has_perm(opts.app_label + '.' + opts.get_change_permission()) and \
            self.has_generic_permission(request, "change")
    
    def has_delete_permission(self, request):
        opts = self._meta
        if request.user.is_superuser:
            return True
        return request.user.has_perm(opts.app_label + '.' + opts.get_delete_permission()) and \
            self.has_generic_permission(request, "delete")
    
    def has_publish_permission(self, request):
        return self.has_generic_permission(request, "publish")
    
    def has_advanced_settings_permission(self, request):
        return self.has_generic_permission(request, "advanced_settings")
    
    def has_change_permissions_permission(self, request):
        """Has user ability to change permissions for current page?
        """
        return self.has_generic_permission(request, "change_permissions")
    
    def has_add_permission(self, request):
        """Has user ability to add page under current page?
        """
        return self.has_generic_permission(request, "add")
    
    def has_moderate_permission(self, request):
        """Has user ability to moderate current page? If moderation isn't 
        installed, nobody can moderate.
        """
        if not settings.CMS_MODERATOR:
            return False
        return self.has_generic_permission(request, "moderate")
    
    def has_move_page_permission(self, request):
        return False
    
    def get_moderator_queryset(self):
        return NewsItem.objects.all()
    
    def has_generic_permission(self, request, perm_type):
        """
        Return true if the current user has permission on the page.
        Return the string 'All' if the user has all rights.
        """
        att_name = "permission_%s_cache" % perm_type
        if not hasattr(self, "permission_user_cache") or not hasattr(self, att_name) \
            or request.user.pk != self.permission_user_cache.pk:
            from cms.utils.permissions import has_generic_permission
            self.permission_user_cache = request.user
            setattr(self, att_name, True)
            #setattr(self, att_name, has_generic_permission(self.id, request.user, perm_type, self.site_id))
            if getattr(self, att_name):
                self.permission_edit_cache = True
                
        return getattr(self, att_name)

class LatestNewsPlugin(CMSPlugin):
    limit = models.PositiveSmallIntegerField(default=0)
    tags = TagField()
    
    def __unicode__(self):
        if self.tags:
            return 'Latest news for: %s' % (str(self.tags),)
        
        return 'Latest news'
    
    def items(self):
        log.debug('%s.items()' % (repr(self),))
        qs = NewsItem.site_objects.filter(published=True)
        tags = Tag.objects.get_for_object(self)
        
        if tags:
            qs = TaggedItem.objects.get_by_model(qs, tags)
        
        if self.limit > 0:
            qs = qs[:self.limit]
        
        return qs
    
    @property
    def render_template(self):
        log.debug('%s.render_template()' % (repr(self),))
        return select_template([
            'cms/plugins/newsy/%s-latest.html' % (self.placeholder.slot.lower(),),
            'cms/plugins/newsy/latest.html'])
    
    def copy_relations(self, oldinstance):
        log.debug('%s.copy_relations(%s)' % (repr(self), repr(oldinstance),))
        self.tags = oldinstance.tags
