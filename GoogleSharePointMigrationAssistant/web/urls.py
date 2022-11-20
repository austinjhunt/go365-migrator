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

    path('create-migration', CreateMigrationView.as_view(), name='create-migration'),
    path('list-migrations', ListMigrationsView.as_view(), name='list-migrations')
]
