""" Utility methods used by Views """
from msal import ConfidentialClientApplication, SerializableTokenCache
from django.core.cache import cache as django_cache
from django.conf import settings
from django.shortcuts import redirect
import requests
import random 
from urllib.parse import quote
from string import ascii_letters, digits
from ..models import AdministrationSettings
import logging 
logger = logging.getLogger(__name__)

def get_random_value(length):
    return ''.join(random.choices(ascii_letters + digits, k=length))


def serialize(object):
    """ convert specified object to string of concatenated query parameters """
    return '&'.join([f'{quote(k)}={quote(v)}' for k, v in object.items()])

########################################
### Microsoft 365 Utility Functions ####
########################################

def get_msal_app(cache=None):
    """ Initialize the MSAL confidential client """
    config = django_cache.get('config', AdministrationSettings.objects.first())
    django_cache.set('config', config)
    auth_app = ConfidentialClientApplication(
        config.azure_ad_client_id,
        authority=f'https://login.microsoftonline.com/{config.azure_ad_tenant_id}',
        client_credential=config.azure_ad_client_secret,
        token_cache=cache
    )
    return auth_app

def get_sign_in_flow():
        """ generate a sign-in flow """
        auth_app = get_msal_app()
        return auth_app.initiate_auth_code_flow(
            scopes=settings.AAD_CLIENT_SCOPES,  # for just signing in
            redirect_uri='http://localhost:8000/m365-redirect-uri',
        )

def load_cache(request):
    """ Check for a token cache in the session """
    cache = SerializableTokenCache()
    if request.session.get('m365_token_cache'):
        cache.deserialize(request.session['m365_token_cache'])
    return cache

def save_cache(request, cache: SerializableTokenCache):
    """ if cache has changed, persist back to session """
    if cache.has_state_changed:
        request.session['m365_token_cache'] = cache.serialize()

def get_token_from_code(request):
    """ exchange auth code for access token """
    config = django_cache.get(
        'config', AdministrationSettings.objects.first())
    django_cache.set('config', config)
    cache = load_cache(request)
    auth_app = get_msal_app(cache)
    flow = request.session.pop('m365_auth_flow', {})
    result = auth_app.acquire_token_by_auth_code_flow(flow, request.GET)
    save_cache(request, cache)
    return result

def get_token_from_cache(request):
    result = None
    config = django_cache.get(
        'config', AdministrationSettings.objects.first())
    django_cache.set('config', config)
    cache = load_cache(request)
    auth_app = get_msal_app(cache)
    accounts = auth_app.get_accounts()
    if accounts:
        result = auth_app.acquire_token_silent(
            settings.AAD_CLIENT_SCOPES, account=accounts[0])
        save_cache(request, cache)
    return result

def get_user_profile(request):
    result = get_token_from_cache(request)
    if not result:
        redirect('init-m365-auth')
    response = requests.get(
        url=f'{settings.GRAPH_API_URL}/me',
        headers={'Authorization': f'Bearer {result["access_token"]}'},
    )
    data = response.json()
    msg = {
        'get_user_profile_response': {
            'status_code': response.status_code,
            'data': data
        }
    }
    if response.status_code != 200:
        logger.error(msg)
    else:
        logger.debug(msg)
    return data

def get_user_onedrive_root_children(request, force_refresh=False):
    if 'user_onedrive_root_children' not in request.session or force_refresh: 
        result = get_token_from_cache(request)
        if not result:
            redirect('init-m365-auth')
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/me/drive/root/children',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_user_onedrive_items_response': {
                'status_code': response.status_code,
                'data': data
            }
        }
        if response.status_code != 200:
            logger.error(msg)
            return None 
        else:
            logger.debug(msg)
        data = data['value']
        request.session['user_onedrive_root_children'] = data
         
    else:
        data = request.session.get('user_onedrive_root_children')
    return data


########################################
# End Microsoft 365 Utility Functions #
########################################