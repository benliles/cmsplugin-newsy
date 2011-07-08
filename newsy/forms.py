from django import forms

from newsy.models import NewsItem



class NewsItemAddForm(forms.ModelForm):
    class Meta:
        model = NewsItem
        exclude = ['published', 'publication_date',]

class NewsItemForm(NewsItemAddForm):
    class Meta(NewsItemAddForm.Meta):
        exclude = []