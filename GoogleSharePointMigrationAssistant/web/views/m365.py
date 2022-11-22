from msal import ConfidentialClientApplication, SerializableTokenCache
import requests
import logging
import json
from django.core.cache import cache as django_cache
from django.contrib.auth.models import User
from django.contrib.auth import login
from .util import get_random_value
from django.shortcuts import render, redirect
from django.views.generic import View
from ..models import AdministrationSettings
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_URL = 'https://graph.microsoft.com/v1.0'


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


class MicrosoftSingleSignOnView(View):
    def get_sign_in_flow(self):
        """ generate a sign-in flow """
        auth_app = get_msal_app()
        return auth_app.initiate_auth_code_flow(
            scopes=settings.AZURE_AD_APP_REGISTRATION_SCOPES,  # for just signing in
            redirect_uri='http://localhost:8000/m365-redirect-uri',
        )

    def get(self, request):
        flow = self.get_sign_in_flow()
        try:
            # Save the expected flow so we can use it in the callback
            request.session['m365_auth_flow'] = flow
            # Redirect to the Azure sign-in page
            return redirect(flow['auth_uri'])
        except Exception as e:
            logger.error({
                'm365-single-sign-on-view': {
                    'error': str(e)
                }
            })
            return redirect('login')


class MicrosoftSingleSignOnCallbackView(View):

    def load_cache(self, request):
        """ Check for a token cache in the session """
        cache = SerializableTokenCache()
        if request.session.get('m365_token_cache'):
            cache.deserialize(request.session['m365_token_cache'])
        return cache

    def save_cache(self, request, cache: SerializableTokenCache):
        """ if cache has changed, persist back to session """
        if cache.has_state_changed:
            request.session['m365_token_cache'] = cache.serialize()

    def get_token_from_code(self, request):
        """ exchange auth code for access token """
        config = django_cache.get(
            'config', AdministrationSettings.objects.first())
        django_cache.set('config', config)
        cache = self.load_cache(request)
        auth_app = get_msal_app(cache)
        flow = request.session.pop('m365_auth_flow', {})
        result = auth_app.acquire_token_by_auth_code_flow(flow, request.GET)
        self.save_cache(request, cache)
        return result

    def get_token_from_cache(self, request):
        result = None
        config = django_cache.get(
            'config', AdministrationSettings.objects.first())
        django_cache.set('config', config)
        cache = self.load_cache(request)
        auth_app = get_msal_app(cache)
        accounts = auth_app.get_accounts()
        if accounts:
            result = auth_app.acquire_token_silent(
                settings.AZURE_AD_APP_REGISTRATION_SCOPES, account=accounts[0])
            self.save_cache(request, cache)
        return result

    def get_user_profile(self, request):
        result = self.get_token_from_cache(request)
        if not result:
            redirect('m365-single-sign-on')
        response = requests.get(
            url=f'{GRAPH_URL}/me',
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

    def get(self, request):
        result = self.get_token_from_code(request)
        request.session['m365_user'] = result['id_token_claims']
        logger.debug({
            'm365_user': request.session['m365_user']
        })
        # make graph call
        graph_user_data = self.get_user_profile(request)
        logger.debug({
            'graph_user_data': graph_user_data
        })
        if not 'error' in graph_user_data:
            request.session['m365_user'] = {
                'is_authenticated': True,
                'display_name': graph_user_data['displayName'],
                'email_address': graph_user_data['userPrincipalName'],
                'first_name': graph_user_data['givenName'],
                'last_name': graph_user_data['surname']
            }
            try:
                local_user = User.objects.get(
                    username=graph_user_data['userPrincipalName'])
            except User.DoesNotExist as e:
                # Create a new user
                local_user = User.objects.create_user(
                    username=graph_user_data['userPrincipalName'],
                    first_name=graph_user_data['givenName'],
                    last_name=graph_user_data['surname'],
                    # irrelevant. user will use SSO.
                    password=get_random_value(length=24)
                )

            login(
                request=request,
                user=local_user
            )
            return render(
                request=request,
                template_name='migrations/steps.html',
                context={}
            )
        else:
            return render(
                request=request,
                template_name='error.html',
                context={'error': json.dumps(user)}
            )

        x = {'graph_user_data': {
            '@odata.context': 'https://graph.microsoft.com/v1.0/$metadata#users/$entity',
            'businessPhones': ['+1 1111111111'],
            'displayName': 'Hunt, Austin',
            'givenName': 'Austin',
            'jobTitle': 'Digital Comms Developer',
            'mobilePhone': None,
            'officeLocation': 'Remote',
            'preferredLanguage': None,
            'surname': 'Hunt', 'userPrincipalName':
            'huntaj@cofc.edu', 'id': '908b9339-6510-4f8b-b89e-260ce8b27267'}}
