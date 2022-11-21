from django.views.generic import View 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render 
from ..models import Migration


class ListMigrationsView(View, LoginRequiredMixin): 
    def get(self, request): 
        return render(
            request=request,
            template_name='migrations/list.html', 
            context={
                'migrations': Migration.objects.filter(user=request.user)
            }
        )