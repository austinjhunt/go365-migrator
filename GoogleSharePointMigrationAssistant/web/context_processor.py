from .models import AdministrationSettings
config = AdministrationSettings.objects.first()
def context(request): 
    return {
        'organization_name': config.organization_name,
        'google_oauth_authorized': request.session.get('google_oauth_authorized', False),
        'google_user': request.session.get('google_user', None),
        'm365_user': request.session.get('m365_user', None)
    }