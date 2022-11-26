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

    # migration source selection
    path('use-google-drive-folder-source/<str:item_id>', UseGoogleDriveFolderSourceView.as_view(), name='use-google-drive-folder-source'),
    path('use-google-drive-shared-drive-source/<str:item_id>', UseGoogleDriveSharedDriveSourceView.as_view(), name='use-google-drive-shared-drive-source'),
    path('change-source', ChangeSourceView.as_view(), name='change-source'),

    # migration destination selection 
    path('change-destination', ChangeDestinationView.as_view(), name='change-destination'),
    
    ## ONEDRIVE SELECTED ##
    # folder selection after onedrive chosen as destination
    path('use-onedrive-destination/<str:folder_id>', UseOneDriveDestinationViewSet.as_view({'get': 'get_folder'}), name='use-onedrive-folder-destination'),
    path('use-onedrive-destination', UseOneDriveDestinationViewSet.as_view({'get': 'get_base'}), name='use-onedrive-destination'),
    ## END ONEDRIVE SELECTED ##

    ## SHAREPOINT SELECTED ##
    # folder selection after doc lib selected for sharepoint destination
    path('use-sharepoint-destination/<str:site_id>/<str:doclib_id>/<str:folder_id>', UseSharePointDestinationViewSet.as_view({'get': 'get_folder'}), name='use-sharepoint-destination'),
    # document library selection after sharepoint site selection for sharepoint destination
    path('use-sharepoint-destination/<str:site_id>/<str:doclib_id>', UseSharePointDestinationViewSet.as_view({'get': 'get_doclib'}), name='use-sharepoint-destination'),
    # site selection for sharepoint destination 
    path('use-sharepoint-destination/<str:site_id>', UseSharePointDestinationViewSet.as_view({'get': 'get_site'}), name='use-sharepoint-destination'),
    # once sharepoint destination is selected
    path('use-sharepoint-destination', UseSharePointDestinationView.as_view(), name='use-sharepoint-destination'),
    ## END SHAREPOINT SELECTED
  
    # scan before migrating
    path('scan-source', ScanSourceDataView.as_view(), name='scan-source'),
    path('scan-source-report/listen/<slug:migration_id>/', ScanSourceReportListenView.as_view(), name='scan-source-report-listen'),
    path('scan-source-report/<slug:migration_id>', ScanSourceReportView.as_view(), name='scan-source-report'),
    
    path('start-migration/<slug:migration_id>', StartMigrationView.as_view(), name='start-migration'),

    path('migration-state-poll/<slug:migration_id>/', MigrationStatePollView.as_view(), name='get-migration-state'),

]
