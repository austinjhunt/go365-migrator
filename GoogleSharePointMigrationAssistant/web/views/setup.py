from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
import logging 
from .google import get_google_drive_content
logger = logging.getLogger(__name__)


class SetupView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        google_drive_content = None
        context = {}

        if not 'google_user' in request.session:
            step = 'google_login'

        elif not 'm365_user' in request.session:
            step = 'm365_login'

        elif not 'source_selected' in request.session or not request.session['source_selected']:
            step = 'select_source'
            google_drive_content = get_google_drive_content(request)
            request.session['google_drive_content'] = google_drive_content
            context['google_drive_content'] = google_drive_content

        elif not 'destination_selected' in request.session or not request.session['destination_selected']:
            step = 'select_destination'
            context['source_selected'] = request.session['source_selected']

        elif not 'migration_started' in request.session:
            step = 'start_scan'
            context['source_selected'] = request.session['source_selected']
            context['destination_selected'] = request.session['destination_selected']

        context['step'] = step 
        return render(
            request=request,
            template_name='next-steps.html',
            context=context
        )
