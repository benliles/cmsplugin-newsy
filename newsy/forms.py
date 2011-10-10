from django import forms

#from tagging.fields import TagField

from newsy.models import NewsItem



class NewsItemAddForm(forms.ModelForm):
    class Meta:
        model = NewsItem
        exclude = ['published', 'publication_date',]

class NewsItemForm(NewsItemAddForm):
    title = forms.CharField(widget=forms.TextInput(attrs={'size': 96}),
                            required=True)
    tags = forms.CharField(widget=forms.TextInput(attrs={'size': 96}))
    short_title = forms.CharField(widget=forms.TextInput(attrs={'size': 96}))
    page_title = forms.CharField(widget=forms.TextInput(attrs={'size': 96}))
    
    
    class Meta(NewsItemAddForm.Meta):
        exclude = []