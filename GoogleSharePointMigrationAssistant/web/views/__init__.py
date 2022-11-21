""" Views for web application"""
from .auth import SignUpView, CustomLoginView, LogoutView, MicrosoftSingleSignOnView
from .base import HomeView
from .migrations import ListMigrationsView
from .setup import SetupView
from .google import InitializeGoogleOAuthView, GoogleOAuthRedirectUri
