"""GoogleSharePointMigrationAssistant URL Configuration"""
from django.urls import path
from django.contrib.auth.decorators import login_required
from .views import *
urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    # Account management
    path('login', CustomLoginView.as_view(), name='login'),
    path('logout', login_required(LogoutView.as_view()), name='logout'),
    path('signup', SignUpView.as_view(), name='signup'),

    # SSO - Microsoft Log In 
    path('init-m365-auth', MicrosoftSingleSignOnView.as_view(), name='init-m365-auth'),
    path('m365-redirect-uri', MicrosoftSingleSignOnCallbackView.as_view(), name='m365-redirect-uri'),

    path('setup', SetupView.as_view(), name='setup'),
    path('list-migrations', ListMigrationsView.as_view(), name='list-migrations'),

    # Google Oauth
    path('init-google-auth', InitializeGoogleOAuthView.as_view(), name='init-google-auth'), 
    path('google-oauth-redirect-uri', GoogleOAuthRedirectUri.as_view(), name='google-oauth-redirect-uri'),

    path('confirm-migration-sources/', ConfirmMigrationSourcesView.as_view(), name='confirm-migration-sources'),
]
