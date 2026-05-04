import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from trf.models import TRFRequest

from .services import ProjectService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TRFRequest)
def trf_fully_approved(sender, instance, created, **kwargs):
    """Auto-create a Project when a TRF reaches APPROVED status."""
    if created:
        return
    if instance.status == TRFRequest.Status.APPROVED:
        ProjectService.create_from_trf(instance)
