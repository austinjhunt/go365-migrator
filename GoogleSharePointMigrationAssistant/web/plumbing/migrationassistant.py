import shutil   
import time 
from msal import SerializableTokenCache
from celery import shared_task
from .constants import *  
from .sharepoint import SharePointUploader
from .googletosharepoint import GoogleToSharePoint
from .onedrive import OneDriveUploader
from .base import BaseUtil 
from .notif.notifier import Notifier
from ..models import Migration
from django.contrib.auth.models import User

class MigrationAssistant(BaseUtil):
    def __init__(
        self,
        verbose: bool = False, 
        migration: Migration = None,
        name: str = 'MigrationAssistant',
        google_credentials: dict = {},
        user: User = None,
        m365_token_cache: SerializableTokenCache = None
        ): 
        super().__init__(name=name, verbose=verbose)      
        self.migration = migration
        self.m365_token_cache = m365_token_cache
        self.google_credentials = google_credentials
        self.user = user 
        self.local_temp_dir = name.lower().replace(' ', '')
        self.notify_stakeholders = [{
            "name": f'{self.user.first_name} {self.user.last_name}',
            "email": user.email 
        }]

        self.migration_elapsed_time_seconds = 0 
        self.file_batch_size = FILE_BATCH_SIZE   

        if self.migration.target_type == 'sharepoint_folder': 
            self.uploader = SharePointUploader(
                migration=self.migration,
                local_folder_base_path=self.local_temp_dir,
                use_multithreading=False,
                verbose=verbose,
                m365_token_cache=self.m365_token_cache
            ) 

        elif self.migration.target_type == 'onedrive_folder': 
            self.uploader = OneDriveUploader(
                verbose=verbose, 
                local_folder_base_path=self.local_temp_dir,
                username=self.user.username
            )
            
        self.downloader = GoogleToSharePoint(
            verbose=verbose, 
            uploader=self.uploader,
            local_temp_dir=self.local_temp_dir,
            file_batch_size=FILE_BATCH_SIZE,
            migration=self.migration,
            google_credentials=self.google_credentials
            )

    def set_file_batch_size(self, fbs):
        self.info(f'Setting downloader file batch size to {fbs}') 
        self.downloader.file_batch_size = fbs 
            
    def notify_completion(self): 
        self.notifier = Notifier() 
        self.notifier.notify_completion(
            migration_info=self.migration,  
            num_files_migrated=self.downloader.num_files_downloaded,
            num_files_already_migrated=self.downloader.num_files_already_in_destination,
            num_files_skipped=self.downloader.num_files_skipped,
            total_drive_files=self.downloader.total_drive_files, 
            elapsed_time=self.migration_elapsed_time_seconds) 


    def upload_logs_to_destination(self):
        """ 
        Log files are going to get big. When migration is finished, upload 
        logs to the same destination, adjacent to the folder uploaded during migration. 
        """
        self.info(f'Uploading logs in {LOG_FOLDER_PATH} to sharepoint and then deleting from local system')
        self.shutdown_logging()
        self.uploader.shutdown_logging()  
        self.notifier.shutdown_logging() 
        if self.migration.target_type == 'sharepoint_folder':
            self.uploader.configure(
                migration=self.migration,
                local_temp_dir=self.local_temp_dir,
                use_multithreading=True
            )
            self.uploader.upload(local_folder_base_path=LOG_FOLDER_PATH) 

        elif self.migration.target_type == 'onedrive_folder': 
            self.uploader.num_completed_uploads = 0 
            self.uploader.upload(
                local_folder_base_path=LOG_FOLDER_PATH
            )  

    def migrate(self):
        start = time.time()
        response = self.downloader.migrate()
        if not response: 
            return False 
        self.info(f"{self.downloader.num_files_downloaded} total files downloaded.\n")
        if self.downloader.num_files_skipped > 0:
            self.info(f"{self.downloader.num_files_skipped} total skipped files, not downloaded.")  
        end = time.time()
        elapsed = end - start
        self.migration_elapsed_time_seconds = self.format_elapsed_time_seconds(elapsed)
        return True 

    def scan_data_source(self):
        return self.downloader.scan()

@shared_task
def scan_data_source(migration_id: int = 0, google_credentials: dict = {}, user_id: int = 0):
    """ Scan source data asynchronously """
    user = User.objects.get(id=user_id)
    migration = Migration.objects.get(id=migration_id)
    assistant = MigrationAssistant(
            migration=migration, 
            name=f'Scan-{user.username}', 
            google_credentials=google_credentials,
            user=user
            )
    return assistant.scan_data_source()

@shared_task 
def migrate_data(migration_id: int = 0, google_credentials: dict = {}, user_id: int = 0):
    user = User.objects.get(id=user_id)
    migration = Migration.objects.get(id=migration_id)
    assistant = MigrationAssistant(
        migration=migration,
        name=f'Migration-{user.username}',
        google_credentials=google_credentials,
        user=user 
    )
    return assistant.migrate()
# def clear_logs(assistant: MigrationAssistant = None):
#     print('Clearing logs')
#     if assistant:
#         assistant.shutdown_logging()
#         assistant.uploader.shutdown_logging()
#         assistant.downloader.shutdown_logging() 
#     try:
#         shutil.rmtree(LOG_FOLDER_PATH, ignore_errors=True)
#     except Exception as e:
#         print(f'Failed to remove log directory {LOG_FOLDER_PATH}')
#         print(e)
#     time.sleep(1)