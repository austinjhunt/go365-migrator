from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
import logging 
from .google import get_files, get_shared_drives
logger = logging.getLogger(__name__)


class SetupView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        google_drive_content = None

        if not 'google_user' in request.session:
            step = 'google_login'
        elif not 'm365_user' in request.session:
            step = 'm365_login'
        elif not 'source_selected' in request.session or not request.session['source_selected']:
            step = 'select_source'
            google_drive_content = get_files(request, query="mimeType='application/vnd.google-apps.folder'")
            google_drive_content += get_shared_drives(request)
        elif not 'destination_selected' in request.session or not request.session['destination_selected']:
            step = 'select_destination'
        elif not 'migration_started' in request.session:
            step = 'start_migration'
        return render(
            request=request,
            template_name='next-steps.html',
            context={
                'step': step,
                'google_drive_content': google_drive_content
            }
        )
