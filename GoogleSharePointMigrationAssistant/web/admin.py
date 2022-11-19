from django.contrib import admin
from .models import Profile, Migration, AdministrationSettings, AdministrationSettings_ListAttributeItem
# Register your models here.
for x in [Profile, Migration,AdministrationSettings, AdministrationSettings_ListAttributeItem]:
    admin.site.register(x)