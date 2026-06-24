from django.core.management.base import BaseCommand

from procurement.services import CertificationService


class Command(BaseCommand):
    help = "Send certification renewal reminders for certifications approaching expiry."

    def handle(self, *args, **options):
        sent_count = CertificationService.send_expiry_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} certification reminder(s)."))
