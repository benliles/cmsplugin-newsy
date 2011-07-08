from datetime import datetime

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from newsy.models import NewsItem



@receiver(pre_save, sender=NewsItem)
def set_publication_date_if_published(instance, **kwargs):
    if hasattr(instance, 'published') and instance.published and not instance.publication_date:
        instance.publication_date = datetime.now()

@receiver(post_save, sender=NewsItem)
def update_placeholders(instance, **kwargs):
    instance.rescan_placeholders()