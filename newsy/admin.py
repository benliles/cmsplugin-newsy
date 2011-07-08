from copy import deepcopy
import os.path

from django.conf import settings
from django.contrib import admin
from django.forms import Widget, Textarea, CharField
from django.template.defaultfilters import title
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _

from cms.forms.widgets import PluginEditor
from cms.models import Placeholder, CMSPlugin
from cms.plugin_pool import plugin_pool
from cms.utils import get_template_from_request
from cms.utils.plugins import get_placeholders

from newsy.forms import NewsItemAddForm, NewsItemForm
from newsy.models import NewsItem

if 'reversion' in settings.INSTALLED_APPS:
    import reversion
    from reversion.admin import VersionAdmin as ModelAdmin
else:
    ModelAdmin = admin.ModelAdmin




class NewsItemAdmin(ModelAdmin):
    form = NewsItemForm
    date_hierarchy = 'publication_date'
    list_filter = ['published', 'template', ]
    search_fields = ('title', 'slug', 'short_title', 'page_title', 'description',)
    revision_form_template = "admin/newsy/newsitem/revision_form.html"
    recover_form_template = "admin/newsy/newsitem/recover_form.html"
    
    prepopulated_fields = {"slug": ("title",)}
    
    exclude = []

    add_fieldsets = [
        (None, {
            'fields': ['title', 'slug', 'description', 'sites',
                       'template'],
            'classes': ('general',),
        }),
    ]

    fieldsets = [
        (None, {
            'fields': ['title', 'description', 'sites', 'published'],
            'classes': ('general',),
        }),
        (_('Basic Settings'), {
            'fields': ['template'],
            'classes': ('low',),
            'description': _('Note: This page reloads if you change the selection. Save it first.'),
        }),
        (_('Advanced Settings'), {
            'fields': ['short_title', 'page_title', 'slug', 'publication_date'],
            'classes': ('collapse',),
        }),
    ]
    
    class Media:
        css = {
            'all': [os.path.join(settings.CMS_MEDIA_URL, path) for path in (
                'css/rte.css',
                'css/pages.css',
                'css/change_form.css',
                'css/jquery.dialog.css',
            )]
        }
        js = [os.path.join(settings.CMS_MEDIA_URL, path) for path in (
            'js/lib/jquery.js',
            'js/lib/jquery.query.js',
            'js/lib/ui.core.js',
            'js/lib/ui.dialog.js',

        )]
    
    def get_fieldsets(self, request, obj=None):
        """
        Add fieldsets of placeholders to the list of already existing
        fieldsets.
        """
        placeholders_template = get_template_from_request(request, obj)

        if obj: # edit
            given_fieldsets = deepcopy(self.fieldsets)
            for placeholder_name in sorted(get_placeholders(placeholders_template)):
                name = settings.CMS_PLACEHOLDER_CONF.get("%s %s" % (obj.template, placeholder_name), {}).get("name", None)
                if not name:
                    name = settings.CMS_PLACEHOLDER_CONF.get(placeholder_name, {}).get("name", None)
                if not name:
                    name = placeholder_name
                else:
                    name = _(name)
                given_fieldsets += [(title(name), {'fields':[placeholder_name], 'classes':['plugin-holder']})]
        else: # new page
            given_fieldsets = deepcopy(self.add_fieldsets)

        return given_fieldsets
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Get NewsItemForm for the NewsItem model and modify its fields depending 
        on the request.
        """
        if obj:
            form = super(NewsItemAdmin, self).get_form(request, obj, **kwargs)
            version_id = None
            versioned = False
            if "history" in request.path or 'recover' in request.path:
                versioned = True
                version_id = request.path.split("/")[-2]
        else:
            self.inlines = []
            form = NewsItemAddForm
        
        if obj:
            if settings.NEWSY_TEMPLATES:
                selected_template = get_template_from_request(request, obj)
                template_choices = list(settings.NEWSY_TEMPLATES)
                form.base_fields['template'].choices = template_choices
                form.base_fields['template'].initial = force_unicode(selected_template)
            
            placeholders = get_placeholders(selected_template)
            for placeholder_name in placeholders:
                plugin_list = []
                show_copy = False
                if versioned:
                    from reversion.models import Version
                    version = get_object_or_404(Version, pk=version_id)
                    installed_plugins = plugin_pool.get_all_plugins()
                    plugin_list = []
                    plugins = []
                    bases = {}
                    revs = []
                    for related_version in version.revision.version_set.all():
                        try:
                            rev = related_version.object_version
                        except models.FieldDoesNotExist:
                            # in case the model has changed in the meantime
                            continue
                        else:
                            revs.append(rev)
                    for rev in revs:
                        pobj = rev.object
                        if pobj.__class__ == Placeholder:
                            if pobj.slot == placeholder_name:
                                placeholder = pobj
                                break
                    for rev in revs:
                        pobj = rev.object
                        if pobj.__class__ == CMSPlugin:
                            if pobj.placeholder_id == placeholder.id and not pobj.parent_id:
                                if pobj.get_plugin_class() == CMSPlugin:
                                    plugin_list.append(pobj)
                                else:
                                    bases[int(pobj.pk)] = pobj
                        if hasattr(pobj, "cmsplugin_ptr_id"):
                            plugins.append(pobj)
                    for plugin in plugins:
                        if int(plugin.cmsplugin_ptr_id) in bases:
                            bases[int(plugin.cmsplugin_ptr_id)].placeholder = placeholder
                            bases[int(plugin.cmsplugin_ptr_id)].set_base_attr(plugin)
                            plugin_list.append(plugin)
                else:
                    placeholder, created = obj.placeholders.get_or_create(slot=placeholder_name)
                    installed_plugins = plugin_pool.get_all_plugins(placeholder_name, obj)
                    plugin_list = CMSPlugin.objects.filter(placeholder=placeholder, parent=None).order_by('position')
                widget = PluginEditor(attrs={
                    'installed': installed_plugins,
                    'list': plugin_list,
                    'copy_languages': [],
                    'show_copy':show_copy,
                    'language': '',
                    'placeholder': placeholder
                })
                form.base_fields[placeholder.slot] = CharField(widget=widget, required=False)
        else:
            form.base_fields['template'].initial = settings.NEWSY_TEMPLATES[0][0]
        
        return form
    
    
admin.site.register(NewsItem, NewsItemAdmin)
