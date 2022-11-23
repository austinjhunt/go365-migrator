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
        NEW = "NEW"
        READY = "READY" # waiting
        PROCESSING = "PROCESSING"
        STOPPING = "STOPPING"
        FAILED = "FAILED"
        COMPLETE = "COMPLETE"
    state = models.CharField(
        max_length=20, choices=STATES.choices, default=STATES.NEW, db_index=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    lastmod = models.DateTimeField(auto_now=True)
    num_files = models.IntegerField(default=0)
    num_folders = models.IntegerField(default=0)
    total_size = models.CharField(max_length=32, default='0')
    start_timestamp = models.DateTimeField(auto_now_add=True)
    end_timestamp = models.DateTimeField()

    google_source_name = models.CharField(max_length=128, blank=True, null=True, verbose_name='Name of the source in Google Drive being migrated')
    SHARED_DRIVE = 'SD'
    FOLDER = 'FR'
    GOOGLE_SOURCE_TYPE_CHOICES = [
        (SHARED_DRIVE, 'Shared Drive'),
        (FOLDER, 'Folder')
    ]
    google_source_type = models.CharField(
        max_length=128, 
        default=FOLDER, 
        choices=GOOGLE_SOURCE_TYPE_CHOICES,
        verbose_name='Type of Google source migrated',
    )
    ## FIXME - USE S3 INSTEAD OF LOCAL FILE SYSTEM
    local_temp_dir = models.CharField(max_length=128, null=True, blank=True, verbose_name='Local directory path where files are temporarily housed during migration')

    complete = models.BooleanField(default=False, verbose_name='Whether the migration is complete')
    completion_notification_sent = models.BooleanField(default=False, verbose_name='Whether a post-completion notification has been sent')

    class TARGET_CHOICES(models.TextChoices):
        ONEDRIVE = 'OneDrive'
        SHAREPOINT = 'SharePoint Online Site'
   
    target_type = models.CharField(
        max_length=24,
        default=TARGET_CHOICES.ONEDRIVE,
        choices=TARGET_CHOICES.choices,
        verbose_name='The type of destination to which the data is being migrated'
    )
    # OneDrive details if chosen
    target_onedrive_folder = models.CharField(max_length=256, null=True, blank=True, verbose_name='The folder within OneDrive to which data is being migrated (if OneDrive is the destination)')

    # Sharepoint details if chosen
    target_sharepoint_site = models.URLField(null=True, blank=True, verbose_name='Base URL of the SharePoint site to which data is being migrated (if using a SharePoint site as the destination)')
    target_sharepoint_document_library = models.CharField(max_length=256, null=True, blank=True, verbose_name='Name of the document library to which data is being migrated (if using a SharePoint site as the destination)')
    target_sharepoint_folder = models.CharField(max_length=256, blank=True, null=True, verbose_name='The folder within the above document library to which files are being migrated (if using a SharePoint site as the destination)')

    ## CONSIDER ADDING file_batch_size as IntegerChoices 
    initial_source_scan_complete = models.BooleanField(default=False, verbose_name='Whether the initial scan of the source data is complete')

    @property
    def friendly_description(self):
        """ Output friendly description of migration for front end display"""
        if self.target_type == self.TARGET_CHOICES.ONEDRIVE:
            dest_string = f'{self.target_onedrive_folder} folder in OneDrive'
        elif self.target_type == self.TARGET_CHOICES.SHAREPOINT:
            dest_string = f'SharePoint Site {self.target_sharepoint_site}, Document Library {self.target_sharepoint_document_library}, Folder {self.target_sharepoint_folder} '
        return (
            f'Migrate {self.google_source_type} {self.google_source_name} to {dest_string}. Currently {self.state.lower()}'
        )

    def start_job(self):
        """ Change state of this job to processing and save """
        self.state = self.STATES.PROCESSING
        self.save()

    def save(self, *args, **kwargs):
        """ Customize the save method to trigger the next READY task if there is one (to achieve queue behavior) """
        if self.state == self.STATES.NEW:
            if Migration.objects.filter(state__in=[
                self.STATES.PROCESSING,
                self.STATES.STOPPING
            ]).count() > 0: 
                self.state = self.STATES.READY
            else: 
                self.state = self.STATES.PROCESSING
                
        elif self.state in [
            self.STATES.COMPLETE,
            self.STATES.FAILED
        ]:
            ready_jobs = Migration.objects.filter(state=self.STATES.READY)
            if ready_jobs.count() > 0:
                ready_jobs[0].start_job()
        super(Migration, self).save(*args, **kwargs)

class AdministrationSettings(models.Model):
    class Meta:
        verbose_name = 'Administration Settings'
        verbose_name_plural = 'Administration Settings'

    organization_name = models.CharField(max_length=128, blank=True, null=True)

    # For OAuth-driven migrations (user-driven)
    google_oauth_json_credentials = models.JSONField(null=True, blank=True, verbose_name='Google OAuth Credentials - JSON (Copy and Paste)')
    google_service_account_auth_json_credentials = models.JSONField(null=True, blank=True, verbose_name='Google Service Account Credentials - JSON (Copy and Paste)')


    # SMTP-based email notifications.
    smtp_enable_email_notifications = models.BooleanField(default=False, verbose_name='Do you want to enable email notifications (on migration completion)? If so, the below fields will be required.')
    smtp_username = models.CharField(max_length=64, null=True, blank=True, verbose_name='SMTP Username')
    smtp_password = models.CharField(max_length=64, null=True, blank=True, verbose_name='SMTP Password')
    smtp_port = models.IntegerField(default=587, null=True, blank=True, verbose_name='SMTP Port (Default is 587)')
    smtp_server = models.CharField(max_length=128, null=True, blank=True, verbose_name='SMTP Server / Host (e.g. smtp.office365.com)')
    smtp_subject = models.TextField(default="Google Drive to SharePoint Migration Complete", null=True, blank=True)

    # Twilio 
    twilio_enable_sms_notifications = models.BooleanField(default=False, verbose_name='Do you want to enable SMS notifications for users? If so, the Twilio settings below will be required.')
    twilio_messaging_service_sid = models.CharField(max_length=32, null=True, blank=True, verbose_name='Provide your Twilio Messaging Service SID')
    twilio_account_sid = models.CharField(max_length=32, null=True, blank=True, verbose_name='Provide your Twilio Account SID (from your Twilio account dashboard)')
    twilio_account_auth_token = models.CharField(max_length=32, null=True, blank=True, verbose_name='Provide your Twilio Account Auth Token (from your Twilio account dashboard)')

    # Azure AD / Microsoft AuthN/AuthZ
    azure_ad_client_id = models.CharField(max_length=128, null=True, blank=True, verbose_name='Azure AD App Registration - Application/Client ID')
    azure_ad_client_secret = models.CharField(max_length=128,  null=True, blank=True, verbose_name='Azure AD App Registration - Client Secret')
    azure_ad_tenant_id = models.CharField(max_length=128,  null=True, blank=True, verbose_name='Azure AD App Registration - (Directory) Tenant ID')
