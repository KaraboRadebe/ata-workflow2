from django.contrib import admin
from .models import (
    TRFRequest, Milestone, Expense,
    TRFApproval, AuditEvent, ApproverProfile, NotificationLog,
)


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 1


class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 1


@admin.register(TRFRequest)
class TRFRequestAdmin(admin.ModelAdmin):
    list_display = ("project_name", "status", "submitted_by", "submitted_at", "created_at")
    list_filter = ("status",)
    inlines = [MilestoneInline, ExpenseInline]


@admin.register(TRFApproval)
class TRFApprovalAdmin(admin.ModelAdmin):
    list_display = ("trf", "level", "action", "actor", "acted_at")
    list_filter = ("level", "action")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("trf", "actor", "action", "from_status", "to_status", "timestamp")
    readonly_fields = ("trf", "actor", "action", "from_status", "to_status", "reason", "timestamp")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApproverProfile)
class ApproverProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "level", "is_available", "delegate")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("trf", "channel", "recipient", "result", "sent_at")
    list_filter = ("channel", "result")
