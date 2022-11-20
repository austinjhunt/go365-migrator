from django.db import models
# https://docs.djangoproject.com/en/4.1/topics/i18n/translation/
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=100, default="UTC")

class Migration(models.Model):
    """ Store migration records for users """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    lastmod = models.DateTimeField(auto_now=True)
    num_files = models.IntegerField(default=0)
    num_folders = models.IntegerField(default=0)
    total_size = models.CharField(max_length=32, default='0')
    start_timestamp = models.DateTimeField(auto_now_add=True)
    end_timestamp = models.DateTimeField()

class AdministrationSettings(models.Model):
    # For OAuth-driven migrations (user-driven)
    google_oauth_client_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='Google Service Account - Client ID')
    google_oauth_project_id = models.CharField(max_length=50, verbose_name='Google Service Account - Project ID')
    google_oauth_auth_uri = models.URLField(null=True, blank=True, verbose_name='Google Service Account - Auth URI')
    google_oauth_token_uri = models.URLField(null=True, blank=True, verbose_name='Google Service Account - Token URI')
    google_oauth_auth_provider_x509_cert_url = models.URLField(null=True, blank=True, verbose_name='Google Service Account - Auth Provider X509 Cert URL')
    google_oauth_auth_client_secret = models.CharField(max_length=50, null=True, blank=True, verbose_name='Google Service Account - Client Secret')
    
    # For SVC-account driven migrations (admin-driven). More vulnerable, requires a highly privileged, centralized service account.
    google_service_account_auth_project_id = models.CharField(max_length=128, null=True, blank=True, verbose_name='Google Service Account - Project ID')
    google_service_account_auth_private_key_id = models.CharField(max_length=128, null=True, blank=True, verbose_name='Google Service Account - Private Key ID')
    google_service_account_auth_private_key = models.TextField(null=True, blank=True, verbose_name='Google Service Account - Private Key')
    google_service_account_auth_client_email = models.EmailField(null=True, blank=True, verbose_name='Google Service Account - Client Email')
    google_service_account_auth_client_id = models.CharField(max_length=32, null=True, blank=True, verbose_name='Google Service Account - Client ID')

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


class AdministrationSettings_ListAttributeItem(models.Model):
    """ Cannot really store a list of strings well in a single column so 
    this handles storage of list attributes for administration settings. Store each 
    as separate object linking back to admin settings via foreign key. """
    class ListAttributeType(models.TextChoices):
        
        # OAuth-based (user-controlled)
        GOOGLE_OAUTH_REDIRECT_URI = 'GOARU', _('Google OAuth Redirect URI')
        GOOGLE_OAUTH_JS_ORIGIN = 'GOAJO', _('Google OAuth JS Origin')

        # SVC-based (admin-controlled)
        GOOGLE_SERVICE_ACCOUNT_AUTH_AUTH_URI = 'GSVCAURI', _('Google Service Account Auth URI')
        GOOGLE_SERVICE_ACCOUNT_AUTH_TOKEN_URI = 'GSVCTURI', _('Google Service Account Token URI')
        GOOGLE_SERVICE_ACCOUNT_AUTH_AUTH_PROVIDER_X509_CERT_URL = 'GSVCAPX509URI', _('Google Service Account Auth Provider X509 Cert URL')
        GOOGLE_SERVICE_ACCOUNT_AUTH_CLIENT_X509_CERT_URL = 'GSVCCLIX509URI', _('Google Service Account Client X509 Cert URL')

    administration_settings = models.ForeignKey(
        AdministrationSettings, on_delete=models.CASCADE)
    list_type = models.CharField(
        max_length=32,
        choices=ListAttributeType.choices,
        default=ListAttributeType.GOOGLE_OAUTH_REDIRECT_URI
    )
