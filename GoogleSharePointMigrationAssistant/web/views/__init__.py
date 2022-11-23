""" Views for web application"""
from .auth import SignUpView, CustomLoginView, LogoutView
from .m365 import MicrosoftSingleSignOnView, MicrosoftSingleSignOnCallbackView
from .base import HomeView
from .migrations import ListMigrationsView, ConfirmMigrationSourcesView, UseOneDriveDestinationView, UseSharePointSiteDestinationView
from .setup import SetupView
from .google import InitializeGoogleOAuthView, GoogleOAuthRedirectUri
