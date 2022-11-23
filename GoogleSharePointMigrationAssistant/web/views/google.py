from django.views.generic import View
from django.shortcuts import redirect, render
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import google_auth_oauthlib.flow
from django.core.cache import cache as django_cache
from django.conf import settings
import logging
from ..models import AdministrationSettings
logger = logging.getLogger(__name__)


MIMETYPES = {
    "application/pdf": "PDF",
    "application/x-httpd-php": "PHP",
    "application/vnd.google-apps.audio": "Audio",
    "application/vnd.google-apps.document": "Google Docs",
    "application/vnd.google-apps.drive-sdk": "3rd party shortcut",
    "application/vnd.google-apps.drawing": "Google Drawing",
    "application/vnd.google-apps.file": "Google Drive file",
    "application/vnd.google-apps.folder": "Google Drive folder",
    "application/vnd.google-apps.form": "Google Forms",
    "application/vnd.google-apps.fusiontable": "Google Fusion Tables",
    "application/vnd.google-apps.jam": "Google Jamboard",
    "application/vnd.google-apps.map": "Google My Maps",
    "application/vnd.google-apps.photo": "Google Photo",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/vnd.google-apps.script": "Google Apps Scripts",
    "application/vnd.google-apps.shortcut": "Shortcut",
    "application/vnd.google-apps.site": "Google Sites",
    "application/vnd.google-apps.spreadsheet": "Google Sheets",
    "application/vnd.google-apps.unknown": "Unknown",
    "application/vnd.google-apps.video": "Video",
    "application/msword": "Microsoft Word (.doc/.dot)",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Microsoft Word (.docx)",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template": "Microsoft Word (.dotx)",
    "application/vnd.ms-word.document.macroEnabled.12": "Microsoft Word (.docm)",
    "application/vnd.ms-word.template.macroEnabled.12": "Microsoft Word (.dotm)",
    "application/vnd.ms-excel": "Microsoft Excel (.xls, .xlt, .xla)",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Microsoft Excel (.xlsx)",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.template": "Microsoft Excel (.xltx)",
    "application/vnd.ms-excel.sheet.macroEnabled.12": "Microsoft Excel (.xlsm)",
    "application/vnd.ms-excel.template.macroEnabled.12": "Microsoft Excel (.xltm)",
    "application/vnd.ms-excel.addin.macroEnabled.12": "Microsoft Excel (.xlam)",
    "application/vnd.ms-excel.sheet.binary.macroEnabled.12": "Microsoft Excel (.xlsb)",
    "application/vnd.ms-powerpoint": "Microsoft PowerPoint (.pps, .ppt, .ppa, .pot)",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation":  "Microsoft PowerPoint Presentation (.pptx)",
    "application/vnd.openxmlformats-officedocument.presentationml.template": "Microsoft PowerPoint Template (.potx)",
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow": "Microsoft PowerPoint Presentation Slideshow(.ppsx)",
    "application/vnd.ms-powerpoint.addin.macroEnabled.12": "Microsoft PowerPoint (.ppam)",
    "application/vnd.ms-powerpoint.presentation.macroEnabled.12":  "Microsoft PowerPoint Presentation (.pptm)",
    "application/vnd.ms-powerpoint.template.macroEnabled.12":  "Microsoft PowerPoint Template (.potm)",
    "application/vnd.ms-powerpoint.slideshow.macroEnabled.12":  "Microsoft PowerPoint Slideshow (.ppam)"
}

### UTIL ###


def get_google_credentials_from_session(request):
    return Credentials(**request.session.get('google_credentials'))


def get_shared_drives(request, query=''):
    with build('drive', 'v3', credentials=get_google_credentials_from_session(request)) as drive:
        data = drive.drives().list(q=query).execute()
        if 'drives' in data:
            for f in data['drives']:
                f['mimeTypeFriendly'] = 'Shared Drive'
                request.session[f'google_shared_drive_{f["id"]}'] = f
            return data['drives']
        else:
            logger.error({
                'google_get_drives': {
                    'error': data
                }
            })
            return None


def get_files(request, query=''):
    with build('drive', 'v3',
               credentials=get_google_credentials_from_session(request)) as drive:
        data = drive.files().list(q=query, supportsAllDrives=True,
                                  supportsTeamDrives=True, includeItemsFromAllDrives=True).execute()
        if 'files' in data:
            for f in data['files']:
                if f['mimeType'] in MIMETYPES:
                    f['mimeTypeFriendly'] = MIMETYPES[f['mimeType']]
                else:
                    f['mimeTypeFriendly'] = f['mimeType'].replace(
                        'application/', '')
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    request.session[f'google_folder_{f["id"]}'] = f
            return data['files']
        else:
            logger.error({
                'google_get_files': {
                    'error': data
                }
            })
            return None


def get_google_drive_content(request):
    """ return a unioned list of both folders and shared drives """
    
    if 'google_drive_content2' in request.session:
        google_drive_content = request.session.get('google_drive_content')
    else:
        google_drive_content = get_files(
            request, query="mimeType='application/vnd.google-apps.folder'")
        google_drive_content += get_shared_drives(request)
        request.session['google_drive_content'] = google_drive_content
    return google_drive_content


def get_google_user_data(request):
    with build('drive', 'v3',  credentials=get_google_credentials_from_session(request)) as drive:
        data = drive.about().get(fields='user').execute()
        logger.debug({'get_google_user_data_response': data})
        if 'user' in data:
            return data
        else:
            logger.error({
                'get_google_user_data_response': data,
                'error': 'user_data_missing'
            })
            return None


def start_oauth_flow(request, config):
    """ Start OAuth 2.0 Authorization Code Flow """
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config=config.google_oauth_json_credentials,
        scopes=settings.GCP_CLIENT_SCOPES)
    flow.redirect_uri = config.google_oauth_json_credentials['web']['redirect_uris'][0]
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')
    request.session['google_oauth_state'] = state
    return redirect(authorization_url)


### VIEWS ####
class GoogleOAuthRedirectUri(View):
    def get(self, request):
        config = django_cache.get(
            'config', AdministrationSettings.objects.first())
        if request.GET.get('state', None) == request.session.get('google_oauth_state'):
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config=config.google_oauth_json_credentials,
                scopes=settings.GCP_CLIENT_SCOPES)
            flow.redirect_uri = config.google_oauth_json_credentials['web']['redirect_uris'][0]

            flow.fetch_token(
                code=request.GET.get('code'),
            )
            credentials = flow.credentials
            request.session['google_credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes}

            request.session['google_oauth_authorized'] = True
            user_data = get_google_user_data(request)
            if 'user' in user_data:
                logger.debug({
                    'google-oauth-redirect-uri-view': {
                        'user_data': user_data
                    }
                })
                request.session['google_user'] = {
                    'email_address': user_data['user']['emailAddress'],
                    'display_name': user_data['user']['displayName'],
                    'photo_link': user_data['user']['photoLink']
                }
                return redirect('setup')
            else:
                logger.error({
                    'google-oauth-redirect-uri-view': {
                        'error': 'user_data_missing',
                        'action': 'redirect_to:init-google-auth'
                    }
                })
                return redirect('init-google-auth')
        else:
            logger.error({
                'google-oauth-redirect-uri-view': {
                    'error': 'session_state_mismatch',
                    'action': 'redirect_to:init-google-auth'
                }
            })
            # Returned state does not match session state
            return redirect('init-google-auth')


class InitializeGoogleOAuthView(View):
    def get(self, request):
        config = django_cache.get(
            'config', AdministrationSettings.objects.first())
        django_cache.set('config', config)

        return start_oauth_flow(request=request, config=config)
