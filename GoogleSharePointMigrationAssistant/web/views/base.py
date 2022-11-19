from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
import logging
logger = logging.getLogger()


class HomeView(View):
    def get(self, request):
        return render(
            request,
            template_name='index.html',
            context={}
        )
