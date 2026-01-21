"""
Context processors for the ERP system.
"""
from apps.core.utils import PermissionChecker


def global_context(request):
    """
    Add global context variables to all templates.
    """
    context = {
        'app_name': 'Gearup',
        'current_year': __import__('datetime').datetime.now().year,
    }
    
    if request.user.is_authenticated:
        context['user_permissions'] = PermissionChecker.get_user_permissions(request.user)
        context['is_superuser'] = request.user.is_superuser
    
    return context

