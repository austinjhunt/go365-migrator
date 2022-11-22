from django.views.generic import View
from django.shortcuts import redirect, render
import requests
import json
import logging 
from .util import get_random_value, serialize
from ..models import AdministrationSettings
logger = logging.getLogger(__name__)

config = AdministrationSettings.objects.first()

### UTIL ### 
scopes = [
  "openid profile",
  "https://www.googleapis.com/auth/drive.readonly",
]

def get_files(request):
    response = requests.get(
        'https://www.googleapis.com/drive/v3/files',
        headers={
            'Authorization': request.session.get('google_oauth_access_token'),
            'Accept': 'application/json'
        }
    ).json()
    return response['files']

def refresh_access_token(request): 
    """ Refresh Google OAuth access token """
    response = requests.post(
        url=config.google_oauth_json_credentials['web']['token_uri'],
        headers={
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
        },
        params=json.dumps({
            'client_id': config.google_oauth_json_credentials['web']['client_id'],
            'client_secret': config.google_oauth_json_credentials['web']['client_secret'],
            'refresh_token': request.session.get('google_oauth_refresh_token'),
            'grant_type': 'refresh_token'
        })
    )
    data = response.json()
    logger.debug({
        'refresh_access_token_response': {
            'status_code': response.status_code, 
            'data': data
        }
    })
    request.session['google_oauth_access_token'] = data['access_token']
    request.session['google_oauth_scope'] = data['scope']
    request.session['google_oauth_expires_in'] = data['expires_in']
    
def exchange_auth_code_for_access_token(request):
    """ Use """
    params = {
            'code': request.GET.get('code'),
            'client_id': config.google_oauth_json_credentials['web']['client_id'],
            'client_secret': config.google_oauth_json_credentials['web']['client_secret'],
            'redirect_uri': config.google_oauth_json_credentials['web']['redirect_uris'][0],
            'grant_type': 'authorization_code'
        }
    response = requests.post(
        f"{config.google_oauth_json_credentials['web']['token_uri']}?{serialize(params)}", headers={
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
            })
    data = response.json()
    logger.debug({
        'exchange_auth_code_for_access_token_response': {
            'status_code': response.status_code, 
            'data': data
        }
    })
    request.session['google_oauth_id_token'] = data['id_token']
    request.session['google_oauth_access_token'] = data['access_token']
    request.session['google_oauth_refresh_token'] = data['refresh_token']
    request.session['google_oauth_scope'] = data['scope']
    request.session['google_oauth_expires_in'] = data['expires_in']

def get_google_user_data(request):
    response = requests.get(
        'https://www.googleapis.com/drive/v3/about?fields=user',
        headers={
            'Authorization': f'Bearer {request.session.get("google_oauth_access_token")}',
            'Accept': 'application/json'
        })
    data = response.json()
    logger.debug({
        'get_google_user_data_response': {
            'status_code': response.status_code,
            'data': data
        }
    })
    return data

def start_oauth_flow(request): 
    request.session['google_oauth_state'] = get_random_value(length=24)
    auth_params = {
        'response_type': 'code', # should always be code for basic auth code flow
        'client_id': config.google_oauth_json_credentials['web']['client_id'],
        'access_type': 'offline', # allwo refresh token
        'scope': ' '.join(scopes), 
        'redirect_uri': config.google_oauth_json_credentials['web']['redirect_uris'][0],
        'state': request.session.get('google_oauth_state'),
        'nonce': get_random_value(length=24)
    }
    full_auth_url = f'{config.google_oauth_json_credentials["web"]["auth_uri"]}?{serialize(auth_params)}'
    logger.debug({
        'start_oauth_flow': {
            'auth_params': auth_params, 
            'full_auth_url': full_auth_url
        }
    })
    return redirect(full_auth_url)


### VIEWS ####
class GoogleOAuthRedirectUri(View):
    def get(self, request): 
        if request.GET.get('state', None) == request.session.get('google_oauth_state'):
            request.session['google_oauth_authorized'] = True 
            exchange_auth_code_for_access_token(request)
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
                return render(
                    request=request, 
                    template_name='migrations/steps.html',
                    context={}
                )
            else: 
                logger.error({
                    'google-oauth-redirect-uri-view': {
                        'error': 'user_data_missing',
                        'action': 'redirect_to:start-flow'
                    }
                })
                return redirect('start-flow')
        else:
            logger.error({
                    'google-oauth-redirect-uri-view': {
                        'error': 'session_state_mismatch',
                        'action': 'redirect_to:start-flow'
                    }
                })
            # Returned state does not match session state
            return redirect('start-flow')

class InitializeGoogleOAuthView(View):
    def get(self, request):
        return start_oauth_flow(request)
        
