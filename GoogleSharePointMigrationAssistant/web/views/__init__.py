""" Views for web application"""
from .auth import SignUpView, CustomLoginView, LogoutView
from .base import HomeView
from .migrations import CreateMigrationView