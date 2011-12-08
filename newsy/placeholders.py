# -*- coding: utf-8 -*-
from logging import getLogger

from cms.exceptions import DuplicatePlaceholderWarning
from cms.models import Page
from cms.plugin_rendering import render_plugins
from cms.plugins.utils import get_plugins
from cms.templatetags.cms_tags import Placeholder
from django.contrib.sites.models import Site
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template import NodeList, TextNode, VariableNode, \
    TemplateSyntaxError
from django.template.loader import get_template
from django.template.loader_tags import ConstantIncludeNode, ExtendsNode, \
    BlockNode
import warnings

from newsy.models import NewsItem



log = getLogger('newsy.placeholders')

def get_newsitem_from_placeholder_if_exists(placeholder):
    log.debug('get_newsitem_from_placeholder_if_exists(placeholder=%s)' % 
              (unicode(placeholder),))
    try:
        return NewsItem.objects.get(placeholders=placeholder)
    except (NewsItem.DoesNotExist, NewsItem.MultipleObjectsReturned):
        return None

def render_newsy_placeholder(placeholder, context, name_fallback="Placeholder"):
    """
    Renders plugins for a placeholder on the given page using shallow copies of the 
    given context, and returns a string containing the rendered output.
    """
    log.debug('render_newsy_placeholder(placeholder=%s)' % 
              (unicode(placeholder),))
    request = context.get('request', None)
    context.push()
    plugins = list(get_plugins(request, placeholder))
    page = get_newsitem_from_placeholder_if_exists(placeholder)
    if page:
        template = page.template
    else:
        template = None
    # Add extra context as defined in settings, but do not overwrite existing context variables,
    # since settings are general and database/template are specific
    # TODO this should actually happen as a plugin context processor, but these currently overwrite 
    # existing context -- maybe change this order?
    slot = getattr(placeholder, 'slot', None)
    extra_context = {}
    if slot:
        extra_context = settings.CMS_PLACEHOLDER_CONF.get("%s %s" % (template, slot), {}).get("extra_context", None)
        if not extra_context:
            extra_context = settings.CMS_PLACEHOLDER_CONF.get(slot, {}).get("extra_context", {})
    for key, value in extra_context.items():
        if not key in context:
            context[key] = value

    c = []
    
    processors = None 
    c.extend(render_plugins(plugins, context, placeholder, processors))
    content = "".join(c)
    context.pop()
    return content
