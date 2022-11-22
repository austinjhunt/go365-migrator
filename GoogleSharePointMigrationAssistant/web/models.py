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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    lastmod = models.DateTimeField(auto_now=True)
    num_files = models.IntegerField(default=0)
    num_folders = models.IntegerField(default=0)
    total_size = models.CharField(max_length=32, default='0')
    start_timestamp = models.DateTimeField(auto_now_add=True)
    end_timestamp = models.DateTimeField()

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
