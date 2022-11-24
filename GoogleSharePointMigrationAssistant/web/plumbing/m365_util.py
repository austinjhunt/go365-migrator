""" Utility methods used by Views """
from msal import ConfidentialClientApplication, SerializableTokenCache
from django.core.cache import cache as django_cache
from django.conf import settings
from django.http import HttpRequest
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
        redirect_uri='http://localhost:8000/m365-redirect-uri', #FIXME - do not hardcode
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


def get_token_from_request_session(request: HttpRequest):
    """ Given a request object, obtain a token cache using its .session attribute, 
    then re-save that cache in the session """
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




def get_token_from_cache(cache: SerializableTokenCache = None):
    """ given a serializable token cache, get the MSAL app from it """
    auth_app = get_msal_app(cache)
    accounts = auth_app.get_accounts()
    if accounts:
        result = auth_app.acquire_token_silent(
            settings.AAD_CLIENT_SCOPES, account=accounts[0])
    return result


def get_user_profile(request):
    result = get_token_from_request_session(request)
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

def get_user_onedrive_item_by_id(request, item_id):
    if f'user_onedrive_folder_{item_id}' not in request.session:
        result = get_token_from_request_session(request)
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/me/drive/items/{item_id}',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_user_onedrive_root_children_response': {
                'status_code': response.status_code,
                'data': data
            }
        }
        if response.status_code != 200:
            logger.error(msg)
            return None
        else:
            logger.debug(msg)
        request.session[f'user_onedrive_folder_{item_id}'] = data
    else:
        data = request.session.get(f'user_onedrive_folder_{item_id}')
    return data 

def get_user_onedrive_root_children(request):
    if 'user_onedrive_root_children' not in request.session:
        result = get_token_from_request_session(request)
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/me/drive/root/children',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_user_onedrive_root_children_response': {
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


def get_user_sharepoint_sites(request, site_filter=''):
    """ Allow user to search for sharepoint site. If no site_filter provided, pulls last query result from session.  """
    if 'sharepoint_sites' not in request.session or site_filter:
        result = get_token_from_request_session(request)
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/sites?$search={site_filter}',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_user_sharepoint_sites': {
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
        request.session['sharepoint_sites'] = data
    else:
        data = request.session.get('sharepoint_sites')

    return data

def get_sharepoint_site_by_id(request, site_id):
    """ Allow user to search for sharepoint site. If no site_filter provided, pulls last query result from session.  """
    if f'sharepoint_site_{site_id}' not in request.session:
        result = get_token_from_request_session(request)
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/sites/{site_id}',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_site_by_id_response': {
                'status_code': response.status_code,
                'data': data
            }
        }
        if response.status_code != 200:
            logger.error(msg)
            return None
        else:
            logger.debug(msg)
        request.session[f'sharepoint_site_{site_id}'] = data
    else:
        data = request.session.get(f'sharepoint_site_{site_id}')
    return data

def get_sharepoint_doclib_by_id(request, doclib_id):
    if f'sharepoint_doclib_{doclib_id}' not in request.session:
        result = get_token_from_request_session(request)
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/drives/{doclib_id}',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_doclib_by_id_response': {
                'status_code': response.status_code,
                'data': data
            }
        }
        if response.status_code != 200:
            logger.error(msg)
            return None
        else:
            logger.debug(msg)
        request.session[f'sharepoint_doclib_{doclib_id}'] = data
    else:
        data = request.session.get(f'sharepoint_doclib_{doclib_id}')
    return data

def get_sharepoint_doclib_item_by_id(request, doclib_id, item_id):
    if f'sharepoint_doclib_{doclib_id}_item_{item_id}' not in request.session:
        result = get_token_from_request_session(request)
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/drives/{doclib_id}/items/{item_id}',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_sharepoint_doclib_item_by_id_response': {
                'status_code': response.status_code,
                'doclib_id': doclib_id,
                'item_id': item_id,
                'data': data
            }
        }
        if response.status_code != 200:
            logger.error(msg)
            return None
        else:
            logger.debug(msg)
        request.session[f'sharepoint_doclib_{doclib_id}_item_{item_id}'] = data
    else:
        data = request.session.get(f'sharepoint_doclib_{doclib_id}_item_{item_id}')
    return data

def get_sharepoint_doclib_children_by_id(request, doclib_id):
    """ return children in root folder """
    if f'sharepoint_doclib_{doclib_id}_children' not in request.session:
        result = get_token_from_request_session(request)
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/drives/{doclib_id}/root/children',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_doclib_by_id_response': {
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
        request.session[f'sharepoint_doclib_{doclib_id}_children'] = data
    else:
        data = request.session.get(f'sharepoint_doclib_{doclib_id}_children')
    return data


def get_sharepoint_site_document_libraries(request, site_id=None):
    """ Get document libraries for a site. If no site_id provided, use stored libraries in session. """
    if 'sharepoint_document_libraries' not in request.session or site_id:
        result = get_token_from_request_session(request)
        response = requests.get(
            url=f'{settings.GRAPH_API_URL}/sites/{site_id}/drives',
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        )
        data = response.json()
        msg = {
            'get_site_document_libraries': {
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
        request.session['sharepoint_document_libraries'] = data
    else:
        data = request.session.get('sharepoint_document_libraries')
    return data

########################################
# End Microsoft 365 Utility Functions #
########################################
