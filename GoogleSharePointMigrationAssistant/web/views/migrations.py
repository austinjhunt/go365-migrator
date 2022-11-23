from django.views.generic import View 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.http import JsonResponse
import logging 
import json
from ..models import Migration
from .util import get_user_onedrive_root_children

logger = logging.getLogger(__name__)

class ListMigrationsView(View, LoginRequiredMixin): 
    def get(self, request): 
        return render(
            request=request,
            template_name='migrations/list.html', 
            context={
                'migrations': Migration.objects.filter(user=request.user)
            }
        )


class StartMigrationView(View, LoginRequiredMixin):
    def get(self, request):
        pass 

class ConfirmMigrationSourcesView(View, LoginRequiredMixin):
    def post(self, request): 
        data = json.loads(request.body.decode("utf-8"))
        if 'selections' in data:
            request.session['source_selected'] = data.get('selections')
            data = {'success': 'selections_confirmed'}
        else: 
            data = {'error': 'selections not provided'}
        return JsonResponse(data)

class UseSharePointSiteDestinationView(View, LoginRequiredMixin):
    def get(self, request): 
        return render(
            request=request, 
            template_name='destinations/sharepoint-sites.html',
            context={}
        )


class UseOneDriveDestinationView(View, LoginRequiredMixin):
    def get(self, request): 
        return render(
            request=request,
            template_name='destinations/onedrive.html',
            context={
                'folders': [el for el in get_user_onedrive_root_children(request) if 'folder' in el]
            }
        )

class UseOneDriveFolderDestinationView(View, LoginRequiredMixin):
    def get(self, request, folder_id): 
        request.session['destination_selected'] = {
            'onedrive_folder': folder_id
        }
        return redirect('setup')