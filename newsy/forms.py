from re import compile

from django import forms
from django.contrib.sites.models import Site
from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _

from newsy.models import NewsItem



validate_slug = RegexValidator(compile(r'^[-a-z0-9]+$'),
    u"Enter a valid 'slug' consisting of lowercase letters, numbers, "
      "underscores or hyphens.", 'invalid')

class NewsItemAddForm(forms.ModelForm):
    class Meta:
        model = NewsItem
        exclude = ['published', 'publication_date',]

class NewsItemForm(NewsItemAddForm):
    title = forms.CharField(widget=forms.TextInput(attrs={'size': 96}),
                            required=True)
    tags = forms.CharField(widget=forms.TextInput(attrs={'size': 96}),
        required=False)
    short_title = forms.CharField(widget=forms.TextInput(attrs={'size': 96}),
        required=False)
    page_title = forms.CharField(widget=forms.TextInput(attrs={'size': 96}),
        required=False)
    slug = forms.CharField(required=True, validators=[validate_slug])
    sites = forms.ModelMultipleChoiceField(queryset=Site.objects.all(),
        widget=forms.CheckboxSelectMultiple())
    class Meta(NewsItemAddForm.Meta):
        exclude = []
