from django.views.generic import View
from django.shortcuts import redirect, render
from string import ascii_letters, digits
from urllib.parse import quote
import random 
import requests
import json
from ..models import AdministrationSettings

config = AdministrationSettings.objects.first()

### UTIL ### 
print(config)
scopes = [
  "openid profile",
  "https://www.googleapis.com/auth/drive.readonly",
]

def get_random_value(length):
    return ''.join(random.choices(ascii_letters + digits, k=length))

def serialize(object):
    """ convert specified object to string of concatenated query parameters """
    return '&'.join([f'{quote(k)}={quote(v)}' for k,v in object.items()])

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
    ).json()
    request.session['google_oauth_access_token'] = response['access_token']
    request.session['google_oauth_scope'] = response['scope']
    request.session['google_oauth_expires_in'] = response['expires_in']
    
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
    print(data)
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
    return redirect(full_auth_url)


### VIEWS ####
class GoogleOAuthRedirectUri(View):
    def get(self, request): 
        print(request.GET.get('state'))
        if request.GET.get('state', None) == request.session.get('google_oauth_state'):
            request.session['google_oauth_authorized'] = True 
            exchange_auth_code_for_access_token(request)
            user_data = get_google_user_data(request)
            if 'user' in user_data:
                request.session['google_oauth_user_email_address'] = user_data['user']['emailAddress']
                request.session['google_oauth_user_photo_link'] = user_data['user']['photoLink']
                request.session['google_oauth_user_display_name'] = user_data['user']['displayName']
            return render(
                request=request, 
                template_name='migrations/steps.html',
                context={}
            )
        else:
            # Returned state does not match session state
            return redirect('start-flow')

class InitializeGoogleOAuthView(View):
    def get(self, request):
        return start_oauth_flow(request)
        
