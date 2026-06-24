from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Run all deployment setup commands'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Running migrations...'))
        call_command('migrate')

        self.stdout.write(self.style.SUCCESS('Collecting static files...'))
        call_command('collectstatic', '--noinput')

        self.stdout.write(self.style.SUCCESS('Deployment setup complete!'))
