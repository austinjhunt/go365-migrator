from django.views.generic import FormView, View
from django.utils.safestring import mark_safe
from ..forms import *


class CustomLoginView(FormView):
    template_name = 'accounts/login.html'
    form_class = LoginForm
    success_url = '/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_class()
        context['searchheader'] = False
        if "next=" in self.request.get_full_path():
            next_url = self.request.get_full_path().split("next=")[-1]
        else:
            next_url = "/"
        context['next'] = mark_safe(next_url)
        return context
    # POST

    def form_valid(self, form):
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(self.request, user)
            # if a next query argument was provided, redirect there
            if 'next' in self.request.POST and self.request.POST.get('next').strip() != '':
                return redirect(self.request.POST.get('next'))
            # else return home
            return redirect('/')
        else:
            form.add_error(None, 'Username or password is incorrect')
            return render(
                self.request,
                template_name=self.template_name,
                context={
                    'form': form,
                }
            )


class SignUpView(FormView):
    form_class = SignupForm
    template_name = 'accounts/signup.html'
    success_url = '/'
    # On GET /signup, send to template_name with new form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_class()
        context['searchheader'] = False
        return context

    def form_valid(self, form):
        username = form.cleaned_data['username']
        password1 = form.cleaned_data['password1']
        password2 = form.cleaned_data['password2']
        if password1 == password2:
            if User.objects.filter(username=username).count() > 0:
                form.add_error(
                    None, f"User with username {username} already exists")
            else:
                user = User.objects.create_user(
                    username=username,
                    password=password1
                )
                user.save()
                prof = Profile(
                    user=user
                )
                prof.save()
                login(self.request, user)
                return redirect('/')
        else:
            form.add_error(
                'password2', 'Password confirmation did not match password')
        return render(
            self.request,
            template_name=self.template_name,
            context={
                'login_form': LoginForm(),
                'signup_form': form,
                # Maintain the same context provided in IndexView since this view goes to same page
                'search_form': SearchPapersForm(),
            }
        )


class LogoutView(View):
    def get(self, request, *args, **kwargs):
        redirectpath = '/'
        if request.user.is_authenticated:
            logout(request)
            if kwargs.get('next', None):
                redirectpath = kwargs.get('next')
        return redirect(redirectpath)
