""" Views for web application"""
from .auth import SignUpView, CustomLoginView, LogoutView
from .m365 import MicrosoftSingleSignOnView, MicrosoftSingleSignOnCallbackView
from .base import HomeView
from .migrations import (
    ListMigrationsView,
    UseGoogleDriveSharedDriveSourceView,
    UseGoogleDriveFolderSourceView,
    UseOneDriveDestinationViewSet,
    UseSharePointDestinationView,
    UseSharePointDestinationViewSet,
    ChangeDestinationView,
    ChangeSourceView,
    StartMigrationView,
    MigrationStatePollView
)
from .setup import SetupView
from .google import InitializeGoogleOAuthView, GoogleOAuthRedirectUri
from .scan import ScanSourceDataView, ScanSourceReportView, ScanSourceReportListenView
