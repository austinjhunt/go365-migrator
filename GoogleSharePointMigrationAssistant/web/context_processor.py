from .models import AdministrationSettings
from django.core.cache import cache as django_cache
def context(request):
    config = django_cache.get('config', AdministrationSettings.objects.first())
    django_cache.set('config', config)
    return {
        'require_sso': config.require_idp_login,
        'organization_name': config.organization_name,
        'google_user': request.session.get('google_user', None),
        'm365_user': request.session.get('m365_user', None)
    }
