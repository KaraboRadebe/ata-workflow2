from django.contrib import admin

from .models import Certification


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = (
        "contact",
        "certification_type",
        "issue_date",
        "expiry_date",
        "reminder_sent",
        "reminder_sent_at",
    )
    list_filter = ("certification_type", "reminder_sent")
    search_fields = ("contact__username", "contact__first_name", "contact__last_name")
