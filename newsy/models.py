from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models
from django.utils.translation import ugettext_lazy as _

from cms.models import Placeholder, Page

from photologue.models import ImageModel

import tagging



class NewsItemThumbnail(ImageModel):
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
    slug = models.SlugField(_("slug"), max_length=255, db_index=True,
                            unique_for_date='published')
    description = models.TextField(_('description'), blank=True, null=True, help_text=_('A short description of the news item'))
    publication_date = models.DateTimeField(_('publication date'), blank=True, null=True, db_index=True, help_text=_('Publication date and time of the news item'))
    published = models.BooleanField(_('published'), default=False)
    sites = models.ManyToManyField(Site)
    placeholders = models.ManyToManyField(Placeholder, editable=False)
    
    class Meta:
        get_latest_by = 'publication_date'
        ordering = ['-publication_date']
    
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

tagging.register(NewsItem)
