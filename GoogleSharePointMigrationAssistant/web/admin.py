from django.contrib import admin
from .models import Profile, Migration, AdministrationSettings
# Register your models here.
for x in [Profile, Migration,AdministrationSettings]:
    admin.site.register(x)