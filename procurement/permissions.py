from functools import wraps
from django.http import HttpResponseForbidden

PROCUREMENT_ROLES = {"PDR", "CDR", "Director", "PC"}


def is_pdr(user):
    return user.is_authenticated and user.role == "PDR"


def is_cdr(user):
    return user.is_authenticated and user.role == "CDR"


def is_director_manager(user):
    return user.is_authenticated and user.role in {"Director", "Admin"}


def is_pc(user):
    return user.is_authenticated and user.role == "PC"


def require_pdr(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_pdr(request.user):
            return HttpResponseForbidden("Only PDR users can perform this action.")
        return view_func(request, *args, **kwargs)
    return wrapper


def require_cdr(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_cdr(request.user):
            return HttpResponseForbidden("Only CDR users can perform this action.")
        return view_func(request, *args, **kwargs)
    return wrapper


def require_director_manager(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_director_manager(request.user):
            return HttpResponseForbidden("Only Director/Manager users can perform this action.")
        return view_func(request, *args, **kwargs)
    return wrapper
