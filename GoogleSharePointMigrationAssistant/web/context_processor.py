from .models import AdministrationSettings
config = AdministrationSettings.objects.first()
def context(request): 
    return {
        'organization_name': config.organization_name,
        'google_oauth_authorized': request.session.get('google_oauth_authorized', None),
        'google_oauth_user_email_address': request.session.get('google_oauth_user_email_address', None),
        'google_oauth_user_photo_link': request.session.get('google_oauth_user_photo_link', None),
        'google_oauth_user_display_name': request.session.get('google_oauth_user_display_name', None)
    }