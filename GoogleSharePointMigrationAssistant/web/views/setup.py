from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render


class SetupView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        return render(
            request=request,
            template_name='next-steps.html',
            context={
            }
        )
