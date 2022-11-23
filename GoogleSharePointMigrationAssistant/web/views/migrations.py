from django.views.generic import View, FormView
from rest_framework import viewsets
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.safestring import mark_safe
from django.shortcuts import render, redirect
import logging
import json
from ..models import Migration
from ..forms import SharePointSiteSearchForm
from .util import (
    get_user_onedrive_root_children, get_user_sharepoint_sites,
    get_sharepoint_site_document_libraries, get_sharepoint_site_by_id,
    get_sharepoint_doclib_by_id, get_sharepoint_doclib_children_by_id,
    get_sharepoint_doclib_item_by_id
)
#from ..plumbing.migrationassistant import MigrationAssistant

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
        # assistant = MigrationAssistant(
        #     verbose=True,
        #     migration={

        #     },
        #     name=f'MigrationAssistant-{request.user.username}',
        #     google_auth_method='oauth',
        # )
        Migration(

        )


class UseGoogleDriveFolderSourceView(View, LoginRequiredMixin):
    """ Called when you select a specific Google Drive item as a source"""

    def get(self, request, item_id):
        data = request.session.get(f'google_folder_{item_id}')
        data['source_type'] = 'folder'
        request.session['source_selected'] = data
        return redirect('setup')


class UseGoogleDriveSharedDriveSourceView(View, LoginRequiredMixin):
    """ Called when you select a specific Google Drive item as a source"""

    def get(self, request, item_id):
        data = request.session.get(f'google_shared_drive_{item_id}')
        data['source_type'] = 'shared_drive'
        request.session['source_selected'] = data

        return redirect('setup')


class ChangeDestinationView(View, LoginRequiredMixin):
    """ View for changing the migration destination. Empty the session variable and redirect back to the setup view. """

    def get(self, request):
        if 'destination_selected' in request.session:
            del request.session['destination_selected']
        return redirect('setup')


class ChangeSourceView(View, LoginRequiredMixin):
    def get(self, request):
        if 'source_selected' in request.session:
            del request.session['source_selected']
            return redirect('setup')

#### SHAREPOINT DESTINATION ####


class UseSharePointDestinationView(FormView, LoginRequiredMixin):
    template_name = 'destinations/select-sharepoint-site.html'
    form_class = SharePointSiteSearchForm
    success_url = '/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_class()
        if "next=" in self.request.get_full_path():
            next_url = self.request.get_full_path().split("next=")[-1]
        else:
            next_url = "/"
        context['next'] = mark_safe(next_url)
        return context

    def form_valid(self, form):
        site_name = form.cleaned_data['site_name']
        matching_sites = get_user_sharepoint_sites(
            request=self.request, site_filter=site_name)
        return render(
            request=self.request,
            template_name=self.template_name,
            context={'form': self.form_class(), 'sharepoint_sites': matching_sites,
                     'site_name': site_name, 'attempted': True}
        )
class UseSharePointDestinationViewSet(viewsets.ViewSet):
    """ View set for sharepoint-related content selection """

    def get_site(self, request, site_id):
        """ return template prompting user to select a document 
        library (drive) from this site """
        return render(
            request=request,
            template_name='destinations/select-sharepoint-doclib.html',
            context={
                'site': get_sharepoint_site_by_id(request=request, site_id=site_id),
                'document_libraries': get_sharepoint_site_document_libraries(request=request, site_id=site_id)
            }
        )

    def get_doclib(self, request, site_id, doclib_id):
        """ return template prompting user to select folder from chosen document library """
        return render(
            request=request, 
            template_name='destinations/select-sharepoint-folder.html',
            context={
                'site': get_sharepoint_site_by_id(request=request, site_id=site_id),
                'document_library': get_sharepoint_doclib_by_id(request=request, doclib_id=doclib_id),
                'children_folders': [el for el in get_sharepoint_doclib_children_by_id(request=request, doclib_id=doclib_id) if 'folder' in el]
            })

    def get_folder(self, request, site_id, doclib_id, folder_id):
        request.session['destination_selected'] = {
            'sharepoint_folder': {
                'site': get_sharepoint_site_by_id(request, site_id=site_id),
                'document_library': get_sharepoint_doclib_by_id(request, doclib_id=doclib_id),
                'folder': get_sharepoint_doclib_item_by_id(request, doclib_id=doclib_id, item_id=folder_id)
            }
        }
        return redirect('setup')

#### END SHAREPOINT DESTINATION ####


#### ONEDRIVE DESTINATION ####

class UseOneDriveDestinationView(View, LoginRequiredMixin):
    def get(self, request):
        return render(
            request=request,
            template_name='destinations/select-onedrive-folder.html',
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

#### END ONEDRIVE DESTINATION ####
