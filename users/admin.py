from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


class UserAdmin(BaseUserAdmin):
    list_display = (
        'username', 
        'first_name', 
        'last_name', 
        'job_title', 
        'approval_level',
        'system_role', 
        'email',
        'is_active'
    )
    list_filter = ('approval_level', 'system_role', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'job_title')
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ATA Profile', {
            'fields': ('job_title', 'approval_level', 'system_role')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('ATA Profile', {
            'fields': ('job_title', 'approval_level', 'system_role')
        }),
    )


admin.site.register(User, UserAdmin)