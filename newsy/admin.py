from copy import deepcopy
import os.path

from django.conf import settings
from django.contrib import admin
from django.db import transaction
from django.forms import Widget, Textarea, CharField
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext
from django.template.defaultfilters import title, escape, force_escape, escapejs
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _

from cms.admin.dialog.views import get_copy_dialog
from cms.forms.widgets import PluginEditor
from cms.models import Placeholder, CMSPlugin
from cms.plugin_pool import plugin_pool
from cms.utils import get_language_from_request
from cms.utils.helpers import make_revision_with_plugins
from cms.utils.plugins import get_placeholders

from newsy.forms import NewsItemAddForm, NewsItemForm
from newsy.models import NewsItem, NewsItemThumbnail

if 'reversion' in settings.INSTALLED_APPS:
    import reversion
    from reversion.admin import VersionAdmin as ModelAdmin
    create_on_success = reversion.revision.create_on_success
else:
    ModelAdmin = admin.ModelAdmin
    create_on_success = lambda x: x



def get_template_from_request(request, obj=None, no_current_page=False):
    """
    Gets a valid template from different sources or falls back to the default
    template.
    """
    template = None
    if len(settings.NEWSY_TEMPLATES) == 1:
        return settings.NEWSY_TEMPLATES[0][0]
    if "template" in request.REQUEST:
        template = request.REQUEST['template']
    if not template and obj is not None:
        template = obj.get_template()
    if not template and not no_current_page and hasattr(request, "current_page"):
        current_page = request.current_page
        if hasattr(current_page, "get_template"):
            template = current_page.get_template()
    if template is not None and template in dict(settings.NEWSY_TEMPLATES).keys():
        return template    
    return settings.NEWSY_TEMPLATES[0][0]

def get_item_from_placeholder_if_exists(placeholder):
    try:
        return NewsItem.objects.get(placeholders=placeholder)
    except (Page.DoesNotExist, MultipleObjectsReturned,):
        return None

def make_revision_with_plugins(obj, user=None, message=None):
    """
    Only add to revision if it is a draft.
    """
    revision_manager = reversion.revision
    
    cls = obj.__class__
    
    if cls in revision_manager._registry:
        
        placeholder_relation = 'newsitem'

        if revision_manager.is_active():
            # add toplevel object to the revision
            revision_manager.add(obj)
            # add plugins and subclasses to the revision
            filters = {'placeholder__%s' % placeholder_relation: obj}
            for plugin in CMSPlugin.objects.filter(**filters):
                plugin_instance, admin = plugin.get_plugin_instance()
                if plugin_instance:
                    revision_manager.add(plugin_instance)
                revision_manager.add(plugin)

class NewsItemThumbnailAdmin(admin.TabularInline):
    model = NewsItemThumbnail
    extra=1
    max_num=1
    verbose_name=_('thumbnail')

class NewsItemAdmin(ModelAdmin):
    form = NewsItemForm
    inlines = [NewsItemThumbnailAdmin]
    date_hierarchy = 'publication_date'
    list_display = ['title', 'published', 'publication_date',]
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
            'fields': ['title', 'description', 'sites', 'published',],
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
    
    def get_urls(self):
        """Get the admin urls
        """
        from django.conf.urls.defaults import patterns, url
        info = "%s_%s" % (self.model._meta.app_label, self.model._meta.module_name)
        pat = lambda regex, fn: url(regex, self.admin_site.admin_view(fn), name='%s_%s' % (info, fn.__name__))

        url_patterns = patterns('',
            pat(r'copy-plugins/$', self.copy_plugins),
            pat(r'add-plugin/$', self.add_plugin),
            pat(r'edit-plugin/([0-9]+)/$', self.edit_plugin),
            pat(r'remove-plugin/$', self.remove_plugin),
            pat(r'move-plugin/$', self.move_plugin),
            pat(r'^([0-9]+)/delete-translation/$', self.delete_translation),
            pat(r'^([0-9]+)/move-page/$', self.move_page),
            pat(r'^([0-9]+)/copy-page/$', self.copy_page),
            pat(r'^([0-9]+)/change-status/$', self.change_status),
            pat(r'^([0-9]+)/change-navigation/$', self.change_innavigation),
            pat(r'^([0-9]+)/jsi18n/$', self.redirect_jsi18n),
            pat(r'^([0-9]+)/permissions/$', self.get_permissions),
            pat(r'^([0-9]+)/moderation-states/$', self.get_moderation_states),
            pat(r'^([0-9]+)/change-moderation/$', self.change_moderation),
            pat(r'^([0-9]+)/approve/$', self.approve_page), # approve page
            pat(r'^([0-9]+)/publish/$', self.publish_page), # publish page
            pat(r'^([0-9]+)/remove-delete-state/$', self.remove_delete_state),
            pat(r'^([0-9]+)/dialog/copy/$', get_copy_dialog), # copy dialog
            pat(r'^([0-9]+)/preview/$', self.preview_page), # copy dialog
            pat(r'^(?P<object_id>\d+)/change_template/$', self.change_template), # copy dialog
        )

        url_patterns = url_patterns + super(NewsItemAdmin, self).get_urls()
        return url_patterns
    
    def redirect_jsi18n(self, request):
        return HttpResponseRedirect(reverse('admin:jsi18n'))
    
    @create_on_success
    def change_template(self, request, object_id):
        page = get_object_or_404(NewsItem, pk=object_id)
        if page.has_change_permission(request):
            to_template = request.POST.get("template", None)
            if to_template in dict(settings.NEWSY_TEMPLATES):
                page.template = to_template
                page.save()
                if "reversion" in settings.INSTALLED_APPS:
                    make_revision_with_plugins(page)
                return HttpResponse(str("ok"))
            else:
                return HttpResponseBadRequest("template not valid")
        else:
            return HttpResponseForbidden()
    
    def get_formsets(self, request, obj=None):
        if obj:
            for inline in self.inline_instances:
                yield inline.get_formset(request, obj)
    
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
    
    def _get_site_languages(self, obj):
        return settings.CMS_LANGUAGES
    
    def change_view(self, request, object_id, extra_context=None):
        """
        The 'change' admin view for the NewsItem model.
        """
        try:
            obj = self.model.objects.get(pk=object_id)
        except self.model.DoesNotExist:
            # Don't raise Http404 just yet, because we haven't checked
            # permissions yet. We don't want an unauthenticated user to be able
            # to determine whether a given object exists.
            obj = None
        else:
            selected_template = get_template_from_request(request, obj)
            moderation_level, moderation_required = 0, False
            
            # if there is a delete request for this page
            moderation_delete_request = False
            
            #activate(user_lang_set)
            extra_context = {
                'placeholders': get_placeholders(selected_template),
                'page': obj,
                'CMS_PERMISSION': settings.CMS_PERMISSION,
                'CMS_MODERATOR': settings.CMS_MODERATOR,
                'ADMIN_MEDIA_URL': settings.ADMIN_MEDIA_PREFIX,
                'has_change_permissions_permission': True,
                'has_moderate_permission': True,
                'moderation_level': moderation_level,
                'moderation_required': moderation_required,
                'moderator_should_approve': False,
                'moderation_delete_request': moderation_delete_request,
                'show_delete_translation': False,
                'current_site_id': settings.SITE_ID,
                'language': get_language_from_request(request, obj),
                'language_tabs': self._get_site_languages(obj),
                'show_language_tabs': False
            }
        
        return super(NewsItemAdmin, self).change_view(request, object_id, extra_context)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        # add context variables
        filled_languages = []
        if obj:
            filled_languages = []
        allowed_languages = [l[0] for l in self._get_site_languages(obj)]
        context.update({
            'filled_languages': [l for l in filled_languages if l in allowed_languages],
        })
        return super(NewsItemAdmin, self).render_change_form(request, context, add, change, form_url, obj)
    
    
    @transaction.commit_on_success
    def move_page(self, request, page_id, extra_context=None):
        """
        Move the page to the requested target, at the given position
        """
        raise Http404()
        target = request.POST.get('target', None)
        position = request.POST.get('position', None)
        if target is None or position is None:
            return HttpResponseRedirect('../../')

        try:
            page = self.model.objects.get(pk=page_id)
            target = self.model.objects.get(pk=target)
        except self.model.DoesNotExist:
            return HttpResponseBadRequest("error")

        # does he haves permissions to do this...?
        if not page.has_move_page_permission(request) or \
            not target.has_add_permission(request):
                return HttpResponseForbidden("Denied")

        # move page
        page.move_page(target, position)
        
        if "reversion" in settings.INSTALLED_APPS:
            make_revision_with_plugins(page)
            
        return render_admin_menu_item(request, page)

    def get_permissions(self, request, page_id):
        raise Http404()
        page = get_object_or_404(NewsItem, id=page_id)

        can_change_list = NewsItem.permissions.get_change_id_list(request.user, page.site_id)

        global_page_permissions = GlobalNewsItemPermission.objects.filter(sites__in=[page.site_id])
        page_permissions = NewsItemPermission.objects.for_page(page)
        permissions = list(global_page_permissions) + list(page_permissions)

        # does he can change global permissions ?
        has_global = has_global_change_permissions_permission(request.user)

        permission_set = []
        for permission in permissions:
            if isinstance(permission, GlobalNewsItemPermission):
                if has_global:
                    permission_set.append([(True, True), permission])
                else:
                    permission_set.append([(True, False), permission])
            else:
                if can_change_list == NewsItemPermissionsPermissionManager.GRANT_ALL:
                    can_change = True
                else:
                    can_change = permission.page_id in can_change_list
                permission_set.append([(False, can_change), permission])

        context = {
            'page': page,
            'permission_set': permission_set,
        }
        return render_to_response('admin/cms/page/permissions.html', context)

    @transaction.commit_on_success
    def copy_page(self, request, page_id, extra_context=None):
        """
        Copy the page and all its plugins and descendants to the requested target, at the given position
        """
        raise Http404()
        context = {}
        page = NewsItem.objects.get(pk=page_id)

        target = request.POST.get('target', None)
        position = request.POST.get('position', None)
        site = request.POST.get('site', None)
        if target is not None and position is not None and site is not None:
            try:
                target = self.model.objects.get(pk=target)
                # does he haves permissions to copy this page under target?
                assert target.has_add_permission(request)
                site = Site.objects.get(pk=site)
            except (ObjectDoesNotExist, AssertionError):
                return HttpResponse("error")
                #context.update({'error': _('NewsItem could not been moved.')})
            else:
                kwargs = {
                    'copy_permissions': request.REQUEST.get('copy_permissions', False),
                    'copy_moderation': request.REQUEST.get('copy_moderation', False)
                }
                page.copy_page(target, site, position, **kwargs)
                return HttpResponse("ok")
                #return self.list_pages(request,
                #    template_name='admin/cms/page/change_list_tree.html')
        context.update(extra_context or {})
        return HttpResponseRedirect('../../')

    def get_moderation_states(self, request, page_id):
        """Returns moderation messsages. Is loaded over ajax to inline-group
        element in change form view.
        """
        raise Http404()
        page = get_object_or_404(NewsItem, id=page_id)
        if not page.has_moderate_permission(request):
            raise Http404()

        context = {
            'page': page,
        }
        return render_to_response('admin/cms/page/moderation_messages.html', context)

    @transaction.commit_on_success
    def approve_page(self, request, page_id):
        """Approve changes on current page by user from request.
        """
        raise Http404()
        #TODO: change to POST method !! get is not safe
        page = get_object_or_404(NewsItem, id=page_id)
        if not page.has_moderate_permission(request):
            raise Http404()

        approve_page(request, page)

        # Django SQLite bug. Does not convert to string the lazy instances
        from django.utils.translation import ugettext as _
        self.message_user(request, _('NewsItem was successfully approved.'))

        if 'node' in request.REQUEST:
            # if request comes from tree..
            return render_admin_menu_item(request, page)
        referer = request.META.get('HTTP_REFERER', reverse('admin:cms_page_changelist'))
        path = '../../'
        if 'admin' not in referer:
            path = '%s?edit-off' % referer.split('?')[0]
        return HttpResponseRedirect( path )


    @transaction.commit_on_success
    def publish_page(self, request, object_id):
        raise Http404()
        item = get_object_or_404(NewsItem, id=object_id)
        # ensure user has permissions to publish this page
        if not page.has_moderate_permission(request):
            return HttpResponseForbidden("Denied")
        page.publish()
        referer = request.META['HTTP_REFERER']
        path = '../../'
        if 'admin' not in referer:
            path = '%s?edit-off' % referer.split('?')[0]
        return HttpResponseRedirect( path )

    @create_on_success
    def delete_translation(self, request, object_id, extra_context=None):
        raise Http404()
        language = get_language_from_request(request)

        opts = NewsItem._meta
        titleopts = Title._meta
        app_label = titleopts.app_label
        pluginopts = CMSPlugin._meta

        try:
            obj = self.queryset(request).get(pk=unquote(object_id))
        except self.model.DoesNotExist:
            # Don't raise Http404 just yet, because we haven't checked
            # permissions yet. We don't want an unauthenticated user to be able
            # to determine whether a given object exists.
            obj = None

        if not self.has_delete_permission(request, obj):
            raise PermissionDenied

        if obj is None:
            raise Http404(_('%(name)s object with primary key %(key)r does not exist.') % {'name': force_unicode(opts.verbose_name), 'key': escape(object_id)})

        if not len(obj.get_languages()) > 1:
            raise Http404(_('There only exists one translation for this page'))

        titleobj = get_object_or_404(Title, page__id=object_id, language=language)
        plugins = CMSPlugin.objects.filter(placeholder__page__id=object_id, language=language)
        
        deleted_objects, perms_needed = get_deleted_objects([titleobj], titleopts, request.user, self.admin_site)
        to_delete_plugins, perms_needed_plugins = get_deleted_objects(plugins, pluginopts, request.user, self.admin_site)
        deleted_objects.append(to_delete_plugins)
        perms_needed = set( list(perms_needed) + list(perms_needed_plugins) )
        

        if request.method == 'POST':
            if perms_needed:
                raise PermissionDenied

            message = _('Title and plugins with language %(language)s was deleted') % {
                'language': [name for code, name in settings.CMS_LANGUAGES if code == language][0]}
            self.log_change(request, titleobj, message)
            self.message_user(request, message)

            titleobj.delete()
            for p in plugins:
                p.delete()

            public = obj.publisher_public
            if public:
                public.save()
                
            if "reversion" in settings.INSTALLED_APPS:
                make_revision_with_plugins(obj)
                
            if not self.has_change_permission(request, None):
                return HttpResponseRedirect("../../../../")
            return HttpResponseRedirect("../../")

        context = {
            "title": _("Are you sure?"),
            "object_name": force_unicode(titleopts.verbose_name),
            "object": titleobj,
            "deleted_objects": deleted_objects,
            "perms_lacking": perms_needed,
            "opts": titleopts,
            "root_path": self.admin_site.root_path,
            "app_label": app_label,
        }
        context.update(extra_context or {})
        context_instance = template.RequestContext(request, current_app=self.admin_site.name)
        return render_to_response(self.delete_confirmation_template or [
            "admin/%s/%s/delete_confirmation.html" % (app_label, titleopts.object_name.lower()),
            "admin/%s/delete_confirmation.html" % app_label,
            "admin/delete_confirmation.html"
        ], context, context_instance=context_instance)

    def remove_delete_state(self, request, object_id):
        """Remove all delete action from page states, requires change permission
        """
        raise Http404()
        page = get_object_or_404(NewsItem, id=object_id)
        if not self.has_change_permission(request, page):
            raise PermissionDenied
        page.pagemoderatorstate_set.get_delete_actions().delete()
        page.moderator_state = NewsItem.MODERATOR_NEED_APPROVEMENT
        page.save()
        return HttpResponseRedirect("../../%d/" % page.id)

    def preview_page(self, request, object_id):
        """Redirecting preview function based on draft_id
        """
        raise Http404()
        instance = page = get_object_or_404(NewsItem, id=object_id)
        attrs = "?preview=1"
        if request.REQUEST.get('public', None):
            if not page.publisher_public_id:
                raise Http404
            instance = page.publisher_public
        else:
            attrs += "&draft=1"

        url = instance.get_absolute_url() + attrs

        site = Site.objects.get_current()

        if not site == instance.site:
            url = "http://%s%s" % (instance.site.domain, url)
        return HttpResponseRedirect(url)

    def change_status(self, request, page_id):
        """
        Switch the status of a page
        """
        raise Http404()
        if request.method != 'POST':
            return HttpResponseNotAllowed
        page = get_object_or_404(NewsItem, pk=page_id)
        if page.has_publish_permission(request):
            page.published = not page.published
            page.save()
            return render_admin_menu_item(request, page)
        else:
            return HttpResponseForbidden(unicode(_("You do not have permission to publish this page")))

    def change_innavigation(self, request, page_id):
        """
        Switch the in_navigation of a page
        """
        raise Http404()
        if request.method != 'POST':
            return HttpResponseNotAllowed
        page = get_object_or_404(NewsItem, pk=page_id)
        if page.has_change_permission(request):
            if page.in_navigation:
                page.in_navigation = False
            else:
                page.in_navigation = True
            page.save(force_state=NewsItem.MODERATOR_NEED_APPROVEMENT)
            return render_admin_menu_item(request, page)
        return HttpResponseForbidden(_("You do not have permission to change this page's in_navigation status"))

    @create_on_success
    def add_plugin(self, request):
        '''
        Could be either a page or a parent - if it's a parent we get the page via parent.
        '''
        if 'history' in request.path or 'recover' in request.path:
            return HttpResponse(str("error"))
        if request.method == "POST":
            plugin_type = request.POST['plugin_type']
            placeholder_id = request.POST.get('placeholder', None)
            parent_id = request.POST.get('parent_id', None)
            if placeholder_id:
                placeholder = get_object_or_404(Placeholder, pk=placeholder_id)
                page = get_item_from_placeholder_if_exists(placeholder)
            else:
                placeholder = None
                page = None
            parent = None
            # page add-plugin
            if page:
                language = request.POST['language'] or get_language_from_request(request)
                position = CMSPlugin.objects.filter(language=language, placeholder=placeholder).count()
                limits = settings.CMS_PLACEHOLDER_CONF.get("%s %s" % (page.get_template(), placeholder.slot), {}).get('limits', None)
                if not limits:
                    limits = settings.CMS_PLACEHOLDER_CONF.get(placeholder.slot, {}).get('limits', None)
                if limits:
                    global_limit = limits.get("global")
                    type_limit = limits.get(plugin_type)
                    if global_limit and position >= global_limit:
                        return HttpResponseBadRequest("This placeholder already has the maximum number of plugins")
                    elif type_limit:
                        type_count = CMSPlugin.objects.filter(language=language, placeholder=placeholder, plugin_type=plugin_type).count()
                        if type_count >= type_limit:
                            return HttpResponseBadRequest("This placeholder already has the maximum number allowed %s plugins.'%s'" % plugin_type)
            # in-plugin add-plugin
            elif parent_id:
                parent = get_object_or_404(CMSPlugin, pk=parent_id)
                placeholder = parent.placeholder
                page = get_item_from_placeholder_if_exists(placeholder)
                if not page: # Make sure we do have a page
                    raise Http404
                language = parent.language
                position = None
            # placeholder (non-page) add-plugin
            else:
                # do NOT allow non-page placeholders to use this method, they
                # should use their respective admin!
                raise Http404
            
            if not page.has_change_permission(request):
                # we raise a 404 instead of 403 for a slightly improved security
                # and to be consistent with placeholder admin
                raise Http404

            # Sanity check to make sure we're not getting bogus values from JavaScript:
            if not language or not language in [ l[0] for l in settings.LANGUAGES ]:
                return HttpResponseBadRequest(unicode(_("Language must be set to a supported language!")))

            plugin = CMSPlugin(language=language, plugin_type=plugin_type, position=position, placeholder=placeholder)

            if parent:
                plugin.parent = parent
            plugin.save()
            
            if 'reversion' in settings.INSTALLED_APPS and page:
                make_revision_with_plugins(page)
                reversion.revision.user = request.user
                plugin_name = unicode(plugin_pool.get_plugin(plugin_type).name)
                reversion.revision.comment = unicode(_(u"%(plugin_name)s plugin added to %(placeholder)s") % {'plugin_name':plugin_name, 'placeholder':placeholder})
                
            return HttpResponse(str(plugin.pk))
        raise Http404

    @create_on_success
    @transaction.commit_on_success
    def copy_plugins(self, request):
        if 'history' in request.path or 'recover' in request.path:
            return HttpResponse(str("error"))
        if request.method == "POST":
            copy_from = request.POST['copy_from']
            placeholder_id = request.POST['placeholder']
            placeholder = get_object_or_404(Placeholder, pk=placeholder_id)
            page = get_item_from_placeholder_if_exists(placeholder)
            language = request.POST['language'] or get_language_from_request(request)

            if not page.has_change_permission(request):
                return HttpResponseForbidden(_("You do not have permission to change this page"))
            if not language or not language in [ l[0] for l in settings.CMS_LANGUAGES ]:
                return HttpResponseBadRequest(_("Language must be set to a supported language!"))
            if language == copy_from:
                return HttpResponseBadRequest(_("Language must be different than the copied language!"))
            plugins = list(placeholder.cmsplugin_set.filter(language=copy_from).order_by('tree_id', '-rght'))
            
            copy_plugins_to(plugins, placeholder, language)
            
            if page and "reversion" in settings.INSTALLED_APPS:
                make_revision_with_plugins(page)
                reversion.revision.user = request.user
                reversion.revision.comment = _(u"Copied %(language)s plugins to %(placeholder)s") % {'language':dict(settings.LANGUAGES)[language], 'placeholder':placeholder}
                
            plugin_list = CMSPlugin.objects.filter(language=language, placeholder=placeholder, parent=None).order_by('position')
            return render_to_response('admin/cms/page/widgets/plugin_item.html', {'plugin_list':plugin_list}, RequestContext(request))
        raise Http404

    @create_on_success
    def edit_plugin(self, request, plugin_id):
        plugin_id = int(plugin_id)
        if not 'history' in request.path and not 'recover' in request.path:
            cms_plugin = get_object_or_404(CMSPlugin, pk=plugin_id)
            page = get_item_from_placeholder_if_exists(cms_plugin.placeholder)
            instance, plugin_admin = cms_plugin.get_plugin_instance(self.admin_site)
            if page and not page.has_change_permission(request):
                raise Http404
        else:
            # history view with reversion
            from reversion.models import Version
            pre_edit = request.path.split("/edit-plugin/")[0]
            version_id = pre_edit.split("/")[-1]
            Version.objects.get(pk=version_id)
            version = get_object_or_404(Version, pk=version_id)
            rev_objs = []
            for related_version in version.revision.version_set.all():
                try:
                    rev = related_version.object_version
                except models.FieldDoesNotExist:
                    continue
                else:
                    rev_objs.append(rev.object)
            # TODO: check permissions

            for obj in rev_objs:
                if obj.__class__ == CMSPlugin and obj.pk == plugin_id:
                    cms_plugin = obj
                    break
            inst, plugin_admin = cms_plugin.get_plugin_instance(self.admin_site)
            instance = None
            if cms_plugin.get_plugin_class().model == CMSPlugin:
                instance = cms_plugin
            else:
                for obj in rev_objs:
                    if hasattr(obj, "cmsplugin_ptr_id") and int(obj.cmsplugin_ptr_id) == int(cms_plugin.pk):
                        instance = obj
                        break
            if not instance:
                raise Http404("This plugin is not saved in a revision")

        plugin_admin.cms_plugin_instance = cms_plugin
        try:
            plugin_admin.placeholder = cms_plugin.placeholder # TODO: what for reversion..? should it be inst ...?
        except Placeholder.DoesNotExist:
            pass
        if request.method == "POST":
            # set the continue flag, otherwise will plugin_admin make redirect to list
            # view, which actually does'nt exists
            request.POST['_continue'] = True

        if 'reversion' in settings.INSTALLED_APPS and ('history' in request.path or 'recover' in request.path):
            # in case of looking to history just render the plugin content
            context = RequestContext(request)
            return render_to_response(plugin_admin.render_template, plugin_admin.render(context, instance, plugin_admin.placeholder))


        if not instance:
            # instance doesn't exist, call add view
            response = plugin_admin.add_view(request)

        else:
            # already saved before, call change view
            # we actually have the instance here, but since i won't override
            # change_view method, is better if it will be loaded again, so
            # just pass id to plugin_admin
            response = plugin_admin.change_view(request, str(plugin_id))
        if request.method == "POST" and plugin_admin.object_successfully_changed:
            
            # if reversion is installed, save version of the page plugins
            if 'reversion' in settings.INSTALLED_APPS and page:
                make_revision_with_plugins(page)    
                reversion.revision.user = request.user
                plugin_name = unicode(plugin_pool.get_plugin(cms_plugin.plugin_type).name)
                reversion.revision.comment = _(u"%(plugin_name)s plugin edited at position %(position)s in %(placeholder)s") % {'plugin_name':plugin_name, 'position':cms_plugin.position, 'placeholder': cms_plugin.placeholder.slot}

            # read the saved object from plugin_admin - ugly but works
            saved_object = plugin_admin.saved_object

            context = {
                'CMS_MEDIA_URL': settings.CMS_MEDIA_URL,
                'plugin': saved_object,
                'is_popup': True,
                'name': unicode(saved_object),
                "type": saved_object.get_plugin_name(),
                'plugin_id': plugin_id,
                'icon': force_escape(escapejs(saved_object.get_instance_icon_src())),
                'alt': force_escape(escapejs(saved_object.get_instance_icon_alt())),
            }
            return render_to_response('admin/cms/page/plugin_forms_ok.html', context, RequestContext(request))

        return response

    @create_on_success
    def move_plugin(self, request):
        if request.method == "POST" and not 'history' in request.path:
            pos = 0
            page = None
            success = False
            if 'plugin_id' in request.POST:
                plugin = CMSPlugin.objects.get(pk=int(request.POST['plugin_id']))
                page = get_page_from_plugin_or_404(plugin)
                placeholder_slot = request.POST['placeholder']
                placeholders = get_placeholders(page.get_template())
                if not placeholder_slot in placeholders:
                    return HttpResponse(str("error"))
                placeholder = page.placeholders.get(slot=placeholder_slot)
                plugin.placeholder = placeholder
                # plugin positions are 0 based, so just using count here should give us 'last_position + 1'
                position = CMSPlugin.objects.filter(placeholder=placeholder).count()
                plugin.position = position
                plugin.save()
                success = True
            if 'ids' in request.POST:
                for plugin_id in request.POST['ids'].split("_"):
                    plugin = CMSPlugin.objects.get(pk=plugin_id)
                    page = get_item_from_placeholder_if_exists(plugin.placeholder)

                    if page and not page.has_change_permission(request):
                        raise Http404

                    if plugin.position != pos:
                        plugin.position = pos
                        plugin.save()
                    pos += 1
                success = True
            if not success:
                HttpResponse(str("error"))
                
            if page and 'reversion' in settings.INSTALLED_APPS:
                make_revision_with_plugins(page)
                reversion.revision.user = request.user
                reversion.revision.comment = unicode(_(u"Plugins where moved"))
                
            return HttpResponse(str("ok"))
        else:
            return HttpResponse(str("error"))

    @create_on_success
    def remove_plugin(self, request):
        if request.method == "POST" and not 'history' in request.path:
            plugin_id = request.POST['plugin_id']
            plugin = get_object_or_404(CMSPlugin, pk=plugin_id)
            placeholder = plugin.placeholder
            page = get_item_from_placeholder_if_exists(placeholder)

            if page and not page.has_change_permission(request):
                raise Http404

            if page and settings.CMS_MODERATOR and page.is_under_moderation():
                # delete the draft version of the plugin
                plugin.delete()
                # set the page to require approval and save
                page.moderator_state = NewsItem.MODERATOR_NEED_APPROVEMENT
                page.save()
            else:
                plugin.delete_with_public()

            plugin_name = unicode(plugin_pool.get_plugin(plugin.plugin_type).name)
            comment = _(u"%(plugin_name)s plugin at position %(position)s in %(placeholder)s was deleted.") % {'plugin_name':plugin_name, 'position':plugin.position, 'placeholder':plugin.placeholder}
            
            if page and 'reversion' in settings.INSTALLED_APPS:
                make_revision_with_plugins(page)
                reversion.revision.user = request.user
                reversion.revision.comment = comment
                
            return HttpResponse("%s,%s" % (plugin_id, comment))
        raise Http404

    def change_moderation(self, request, page_id):
        """Called when user clicks on a moderation checkbox in tree vies, so if he
        wants to add/remove/change moderation required by him. Moderate is sum of
        mask values.
        """
        if request.method != 'POST':
            return HttpResponseNotAllowed
        raise Http404
        page = get_object_or_404(NewsItem, id=page_id)
        moderate = request.POST.get('moderate', None)
        if moderate is not None and page.has_moderate_permission(request):
            try:
                moderate = int(moderate)
            except:
                moderate = 0

            if moderate == 0:
                # kill record with moderation which equals zero
                try:
                    page.pagemoderator_set.get(user=request.user).delete()
                except ObjectDoesNotExist:
                    pass
                return render_admin_menu_item(request, page)
            elif moderate <= MASK_PAGE + MASK_CHILDREN + MASK_DESCENDANTS:
                page_moderator, created = page.pagemoderator_set.get_or_create(user=request.user)
                # split value to attributes
                page_moderator.set_decimal(moderate)
                page_moderator.save()
                return render_admin_menu_item(request, page)
        raise Http404
    
    
admin.site.register(NewsItem, NewsItemAdmin)
