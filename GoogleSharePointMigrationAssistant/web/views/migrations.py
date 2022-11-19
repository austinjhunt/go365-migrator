from django.views.generic import View 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render 
from ..forms import CreateMigrationForm

class CreateMigrationView(View, LoginRequiredMixin):
    def get(self, request):
        return render(
            request, 
            template_name='migrations/create.html',
            context={
                'form': CreateMigrationForm()
            }
        )