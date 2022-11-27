from django.test import TestCase, override_settings
from ..models import Migration, User, Profile, AdministrationSettings
from .conf import *

@override_settings(
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
            'OPTIONS': {
                # DO NOT USE CUSTOM CONTEXT PROCESSORS FOR TESTING. THEY BREAK THE TESTS.
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        },
    ]
)
class BaseTest(TestCase):
    def setUp(self):
        config = AdministrationSettings(require_idp_login=False)
        config.save()

    def setup_view(self, view, request, *args, **kwargs):
        """
        Mimic ``as_view()``, but returns view instance.
        Use this function to get view instances on which you can run unit tests,
        by testing specific methods.
        """
        view.request = request
        view.args = args
        view.kwargs = kwargs
        return view


class UserTestCase(BaseTest):
    def setUp(self):
        super(UserTestCase, self).setUp()
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@go365migrator.com',
            password='fakepass')

    def test_profile(self):
        try:
            self.assertIsNotNone(Profile.objects.get(user=self.user))
        except Profile.DoesNotExist:
            self.assertTrue(False)

class LoginTestCase(UserTestCase):
    def test_login_correct(self):
        response = self.client.post(
            '/login', data={'username': 'testuser', 'password': 'fakepass'})
        self.assertEquals(302, response.status_code)

    def test_login_incorrect(self):
        response = self.client.post(
            '/login', data={'username': 'testuser2', 'password': 'fakepass'})
        self.assertNotEquals(302, response.status_code)


class LogoutTestCase(UserTestCase):
    def test_logout(self):
        response = self.client.get('/logout')
        self.assertEquals(302, response.status_code)


class MigrationGoogleSharedDriveTestCase(BaseTest):
    def setUp(self):
        super(MigrationGoogleSharedDriveTestCase, self).setUp()
        user = User.objects.create_user(
            username='testuser',
            email='testuser@go365migrator.com',
            password='fakepass')
        self.migration = Migration(
            user=user,
            num_files=20,
            num_folders=2,
            total_size='1.4GB',
            local_temp_dir=user.username,
            target=TARGET_EXAMPLE,
            google_source=GOOGLE_SHARED_DRIVE_SOURCE
        )


class MigrationGoogleFolderTestCase(BaseTest):
    def setUp(self):
        super(MigrationGoogleFolderTestCase, self).setUp()
        user = User.objects.create_user(
            username='testuser',
            email='testuser@go365migrator.com',
            password='fakepass')
        self.migration = Migration(
            user=user,
            num_files=20, num_folders=2,
            total_size='1.4GB',
            google_source=GOOGLE_FOLDER_SOURCE,
            target=TARGET_EXAMPLE
        )
        self.migration.save()

    def test_source_type(self):
        val = self.migration.source_type
        self.assertEquals(val, 'folder')

    def test_source_name(self):
        val = self.migration.source_name
        self.assertEquals(val, 'really cool folder')

    def test_source_id(self):
        val = self.migration.source_id
        self.assertEquals(val, 'scoobydoobydoo-folder')

    def test_target_type(self):
        val = self.migration.target_type
        self.assertEquals(val, 'sharepoint_folder')

    def test_target_folder_id(self):
        val = self.migration.target_folder_id
        self.assertEquals(val, 'folder-guid')

    def test_target_folder_name(self):
        val = self.migration.target_folder_name
        self.assertEquals(val, 'My Folder 1')

    def test_target_document_library_id(self):
        val = self.migration.target_document_library_id
        self.assertEquals(val, 'document-library-guid')
    
    def test_target_document_library_name(self):
        val = self.migration.target_document_library_name
        self.assertEquals(val, 'My Test Doc Lib')
    
    def test_target_site_id(self):
        val = self.migration.target_site_id
        self.assertEquals(val, 'org.sharepoint.com,longid,longid')
    
    def test_target_site_name(self):
        val = self.migration.target_site_name
        self.assertEquals(val, 'this-is-the-site-name')
    
    def test_target_site_display_name(self):
        val = self.migration.target_site_display_name
        self.assertEquals(val, 'SharePoint Online Site Display Name')
    
    def test_target_site_url(self):
        val = self.migration.target_site_url
        self.assertEquals(val, 'https://org.sharepoint.com/sites/this-is-the-site-name')
    
    def test_job_status(self):
        val = self.migration.job_status
        self.assertEquals(val, 'Waiting to scan source data')
