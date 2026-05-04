from django.core.exceptions import PermissionDenied

# Project Manager roles - these users can edit projects and milestones
PROJECT_MANAGER_ROLES = {'PC', 'PDR', 'CDR', 'Ops', 'Director', 'Admin'}

def is_project_manager(user):
    """Check if user has project manager permissions"""
    if not user.is_authenticated:
        return False
    return user.system_role in PROJECT_MANAGER_ROLES

def is_sales_user(user):
    """Check if user is a sales user"""
    if not user.is_authenticated:
        return False
    return user.system_role == 'Sales'

def require_project_manager(view_func):
    """Decorator to require project manager role"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not is_project_manager(request.user):
            raise PermissionDenied("You do not have permission to perform this action.")
        return view_func(request, *args, **kwargs)
    return wrapper