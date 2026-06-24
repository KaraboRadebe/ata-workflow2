from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Run all deployment setup commands: migrate, collect static, and ensure admin user exists'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Step 1: Running migrations...'))
        try:
            call_command('migrate', verbosity=2)
            self.stdout.write(self.style.SUCCESS('✓ Migrations completed'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Migration error: {e}'))
            return

        self.stdout.write(self.style.SUCCESS('Step 2: Collecting static files...'))
        try:
            call_command('collectstatic', '--noinput', verbosity=1)
            self.stdout.write(self.style.SUCCESS('✓ Static files collected'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠ Static files error (non-critical): {e}'))

        self.stdout.write(self.style.SUCCESS('Step 3: Ensuring admin user exists...'))
        User = get_user_model()
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@ata.com',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('ChangeMe123!')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('✓ Admin user created: admin / ChangeMe123!'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Admin user already exists: {admin_user.username}'))

        self.stdout.write(self.style.SUCCESS('\n✅ Deployment setup complete!'))
        self.stdout.write(self.style.WARNING('\n⚠️  If you just created the admin user, change the password immediately in Django admin.'))
