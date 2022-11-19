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
    google_oauth_client_id = models.CharField(max_length=100)
    google_oauth_project_id = models.CharField(max_length=50)
    google_oauth_auth_uri = models.URLField()
    google_oauth_token_uri = models.URLField()
    google_oauth_auth_provider_x509_cert_url = models.URLField()
    google_oauth_auth_client_secret = models.CharField(max_length=50)


class AdministrationSettings_ListAttributeItem(models.Model):
    """ Cannot really store a list of strings well in a single column so 
    this handles storage of list attributes for administration settings. Store each 
    as separate object linking back to admin settings via foreign key. """
    class ListAttributeType(models.TextChoices):
        GOOGLE_OAUTH_REDIRECT_URI = 'GARU', _('Google OAuth Redirect URI')
        GOOGLE_OAUTH_JS_ORIGIN = 'GAJO', _('Google OAuth JS Origin')

    administration_settings = models.ForeignKey(
        AdministrationSettings, on_delete=models.CASCADE)
    list_type = models.CharField(
        max_length=5,
        choices=ListAttributeType.choices,
        default=ListAttributeType.GOOGLE_OAUTH_REDIRECT_URI
    )
