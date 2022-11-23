
from django.contrib.auth.models import User
from django.contrib.auth import login
from .util import (
    get_random_value, get_sign_in_flow,
    get_user_profile, get_token_from_code
)
from django.shortcuts import render, redirect
from django.views.generic import View
import logging
logger = logging.getLogger(__name__)


class MicrosoftSingleSignOnView(View):
    def get(self, request):
        flow = get_sign_in_flow()
        try:
            request.session['m365_auth_flow'] = flow
            return redirect(flow['auth_uri'])
        except Exception as e:
            logger.error({
                'init-m365-auth-view': {
                    'error': str(e)
                }
            })
            return redirect('login')

class MicrosoftSingleSignOnCallbackView(View):
    
    def get(self, request):
        result = get_token_from_code(request)
        graph_user_data = get_user_profile(request)
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
            return redirect('setup')
        else:
            return render(
                request=request,
                template_name='error.html',
                context={'error': graph_user_data['error']}
            )
