from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("procurement", "0004_paymentrequisition_paymentauditevent_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Certification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("certification_type", models.CharField(choices=[('BLS', 'BLS'), ('ACLS', 'ACLS'), ('PALS', 'PALS'), ('ITLS', 'ITLS')], max_length=10)),
                ("issue_date", models.DateField()),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("reminder_sent", models.BooleanField(default=False)),
                ("reminder_sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("contact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="certifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["expiry_date"]},
        ),
    ]
