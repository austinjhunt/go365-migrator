from django.shortcuts import render
from django.views.generic import View

# Create your views here.

class HomeView(View):
    template_name = 'index.html'
    def get(self, request): 
        context = None 
        if request.user.is_authenticated: 
            context = {'user': request.user}
        return render(
            request, 
            template_name='index.html', 
            context=context
        )

class RegisterView(View): 
    pass 

class LoginView(View):
    pass 