from django.db import models
# https://docs.djangoproject.com/en/4.1/topics/i18n/translation/
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User


class Profile(models.Model):
    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=100, default="UTC")


class Migration(models.Model):
    """ Store migration records for users """
    class Meta:
        verbose_name = 'Migration'
        verbose_name_plural = 'Migrations'

    class STATES(models.TextChoices):
        WAITING_TO_SCAN = "Waiting to scan source data"
        SCANNING = "Scanning source data"
        SCAN_COMPLETE = "Source data scan is complete"
        WAITING_TO_MIGRATE = "Waiting to migrate source data to target"
        MIGRATING = "Migrating source data to target"
        MIGRATION_FAILED = "Migration to target failed"
        MIGRATION_COMPLETE = "Migration is complete"
    state = models.CharField(
        max_length=56, choices=STATES.choices, default=STATES.WAITING_TO_SCAN, db_index=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    lastmod = models.DateTimeField(auto_now=True)
    num_files = models.IntegerField(default=0)
    num_folders = models.IntegerField(default=0)
    total_size = models.CharField(max_length=32, default='0')
    start_timestamp = models.DateTimeField(auto_now_add=True)
    end_timestamp = models.DateTimeField(blank=True, null=True)

    google_source = models.JSONField(
        default=dict,
        null=True, blank=True, verbose_name=(
            'JSON object including at minimum id, name, '
            'or type as keys describing the source folder '
            'or shared drive being migrated. Type can be '
            '"shared_drive" or "folder"')
    )
    source_data_scan_result = models.JSONField(
        default=dict,
        null=True, blank=True, 
        verbose_name=(
            'High-level stats about the migration '
            'to be run based on scanning the source '
            'data to be migrated'
        )
    )

    # FIXME/TODO - USE S3 INSTEAD OF LOCAL FILE SYSTEM
    local_temp_dir = models.CharField(
        max_length=128, null=True, blank=True,
        verbose_name=(
            'Local directory path where files are '
            'temporarily housed during migration'))

    complete = models.BooleanField(
        default=False, verbose_name='Whether the migration is complete')
    completion_notification_sent = models.BooleanField(
        default=False, verbose_name='Whether a post-completion notification has been sent')

    target = models.JSONField(
        blank=True, null=True, default=dict, 
        verbose_name=(
            'Information describing either a SharePoint '
            'Site Folder in a Document Library or a OneDrive '
            'Folder for the user OneDrive account')
    )
    # CONSIDER ADDING file_batch_size as IntegerChoices
    initial_source_scan_complete = models.BooleanField(
        default=False, verbose_name='Whether the initial scan of the source data is complete')

    @property
    def friendly_description(self):
        """ Output friendly description of migration for front end display"""
        if self.target['type'] == 'onedrive_folder':
            dest_string = f'the folder {self.target_folder_name} in your OneDrive'
        elif self.target['type'] == 'sharepoint_folder':
            dest_string = (
                f'the folder {self.target_folder_name} in the Document '
                f'Library {self.target_document_library_name} on the '
                f'SharePoint Site {self.target_site_display_name}'
            )
        return (
            f'Migrate {self.source_type} {self.source_name} '
            f'to {dest_string}. Migration job is currently {self.state.lower()}'
        )
    
    
    @property 
    def source_type(self):
        return self.google_source["type"]

    @property 
    def source_name(self):
        return self.google_source["details"]["name"]
    
    @property 
    def source_id(self):
        return self.google_source["details"]["id"]

    @property 
    def target_type(self):
        return self.target["type"]

    @property
    def target_folder(self):
        return self.target["details"]["folder"]

    @property
    def target_folder_name(self):
        return self.target["details"]["folder"]["name"]
    
    @property
    def target_folder_id(self):
        return self.target["details"]["folder"]["id"]

    @property 
    def target_document_library(self):
        return self.target["details"]["document_library"]

    @property 
    def target_document_library_name(self):
        return self.target["details"]["document_library"]["name"]

    @property 
    def target_document_library_id(self):
        return self.target["details"]["document_library"]["id"]

    @property 
    def target_site(self):
        return self.target["details"]["site"]

    @property 
    def target_site_name(self):
        return self.target["details"]["site"]["name"]

    @property 
    def target_site_display_name(self):
        return self.target["details"]["site"]["displayName"]

    @property 
    def target_site_url(self):
        return self.target["details"]["site"]["webUrl"]

    @property 
    def target_site_id(self):
        return self.target["details"]["site"]["id"]

    @property 
    def job_status(self):
        return self.state.capitalize()


class AdministrationSettings(models.Model):
    class Meta:
        verbose_name = 'Administration Settings'
        verbose_name_plural = 'Administration Settings'

    organization_name = models.CharField(max_length=128, blank=True, null=True)

    require_idp_login = models.BooleanField(
        default=False, verbose_name=(
            'Require Single Sign On (login via the IdP). '
            'If true, local login form (username, password) will be disabled.')
    )

    # For OAuth-driven migrations (user-driven)
    google_oauth_json_credentials = models.JSONField(
        default=dict,
        null=True, blank=True, verbose_name='Google OAuth Credentials - JSON (Copy and Paste)')
    google_service_account_auth_json_credentials = models.JSONField(
        default=dict,
        null=True, blank=True, verbose_name='Google Service Account Credentials - JSON (Copy and Paste)')

    # SMTP-based email notifications.
    smtp_enable_email_notifications = models.BooleanField(
        default=False, verbose_name='Enable email notifications (on migration completion)? If enabled, SMTP fields will be required.')
    smtp_username = models.CharField(
        max_length=64, null=True, blank=True, verbose_name='SMTP Username')
    smtp_password = models.CharField(
        max_length=64, null=True, blank=True, verbose_name='SMTP Password')
    smtp_port = models.IntegerField(
        default=587, null=True, blank=True, verbose_name='SMTP Port (Default is 587)')
    smtp_server = models.CharField(max_length=128, null=True, blank=True,
                                   verbose_name='SMTP Server / Host (e.g. smtp.office365.com)')
    smtp_subject = models.TextField(
        default="Google Drive to SharePoint Migration Complete", null=True, blank=True)

    # Twilio
    twilio_enable_sms_notifications = models.BooleanField(
        default=False, verbose_name='Enable SMS notifications for users. If enabled, Twilio settings will be required.')
    twilio_messaging_service_sid = models.CharField(
        max_length=32, null=True, blank=True, verbose_name='Twilio Messaging Service SID')
    twilio_account_sid = models.CharField(max_length=32, null=True, blank=True,
                                          verbose_name='Twilio Account SID (from your Twilio account dashboard)')
    twilio_account_auth_token = models.CharField(
        max_length=32, null=True, blank=True, verbose_name='Twilio Account Auth Token (from your Twilio account dashboard)')

    # Azure AD / Microsoft AuthN/AuthZ
    azure_ad_client_id = models.CharField(
        max_length=128, null=True, blank=True, verbose_name='Azure AD App Registration - Application/Client ID')
    azure_ad_client_secret = models.CharField(
        max_length=128,  null=True, blank=True, verbose_name='Azure AD App Registration - Client Secret')
    azure_ad_tenant_id = models.CharField(
        max_length=128,  null=True, blank=True, verbose_name='Azure AD App Registration - (Directory) Tenant ID')

    onedrive_email_notification_template = models.TextField(
        blank=True, null=True, 
        verbose_name='Email Body Template for Google to OneDrive Migration Email Notification',
        default=""
    )
    onedrive_sms_notification_template = models.TextField(
        blank=True, null=True, 
        verbose_name='SMS Message Template for Google to OneDrive Migration SMS Notification',
        default=""
    )
    sharepoint_email_notification_template = models.TextField(
        blank=True, null=True, 
        verbose_name='Email Body Template for Google to SharePoint Migration Email Notification',
        default=""
    )
    sharepoint_sms_notification_template = models.TextField(
        blank=True, null=True, 
        verbose_name='SMS Message Template for Google to SharePoint Migration SMS Notification',
        default=""
    )