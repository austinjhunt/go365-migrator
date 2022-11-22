from django.views.generic import View 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render 
from django.http import JsonResponse
import logging 
import json
from ..models import Migration
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
        logger.debug(request.POST)
        logger.debug(request.__dict__)
        if 'selections' in data:
            selections = data.get('selections')
            logger.debug({'google_items_to_migrate': selections})
            request.session['google_items_to_migrate'] = selections
            request.session['source_selected'] = True 
            data = {'success': 'selections_confirmed'}
        else: 
            data = {'error': 'selections not provided'}
        return JsonResponse(data)