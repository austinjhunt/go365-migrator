import shutil   
import time 
import time  
from django.http import HttpRequest
from .constants import *  
from .sharepoint import SharePointUploader
from .googledownloader import GoogleToSharePoint
from .onedrive import OneDriveUploader
from .base import BaseLogging 
from .notif.notifier import Notifier
from ..models import Migration

class MigrationAssistant(BaseLogging):
    def __init__(
        self,
        verbose: bool = False, 
        migration: Migration = None,
        name: str = 'MigrationAssistant',
        request: HttpRequest = None
        ): 
        super().__init__(name=name, verbose=verbose)      
        self.migration = migration
        self.request = request
        # FIXME: Use S3
        self.local_temp_dir = name.lower().replace(' ', '')
        self.notify_stakeholders = [{
            "name": f'{self.request.user.first_name} {self.request.user.last_name}', #FIXME - need to populate name with SSO 
            "email": self.request.user.email #fix me too
        }]

        self.migration_elapsed_time_seconds = 0 
        self.file_batch_size = FILE_BATCH_SIZE   

        if self.migration.target_type == 'sharepoint_folder':   
            self.target_document_library = migration['target_document_library']
            self.target_folder = migration['target_folder'] 
            self.uploader = SharePointUploader(
                local_folder_base_path=self.local_temp_dir,
                target_sharepoint_site_url=self.migration.target_site_url,
                target_document_library_name=self.migration.target_document_library_name,
                target_base_folder=self.migration.target_folder_name, # possible problem
                use_multithreading=False,
                verbose=verbose
            ) 

        elif self.migration.target_type == 'onedrive_folder': 
            self.uploader = OneDriveUploader(
                verbose=verbose, 
                local_folder_base_path=self.local_temp_dir,
                username=self.request.user.username
            )
            
        self.downloader = GoogleToSharePoint(
            verbose=verbose, 
            uploader=self.uploader,
            local_temp_dir=self.local_temp_dir,
            file_batch_size=FILE_BATCH_SIZE,
            migration=self.migration,
            request=self.request 
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
                local_folder_base_path=LOG_FOLDER_PATH,
                target_sharepoint_site_url=self.migration.target_site_url, 
                target_document_library_name=self.migration.target_document_library_name,
                target_base_folder=f'{self.migration.target_folder_name}/{self.local_temp_dir.split("/")[-1]}',
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
        # possible source types: file, folder, user_drive, shared_drive
        response = self.downloader.download(
            entity_type=self.migration.source_type,
            entity_name=self.migration.source_name
        ) 
        if not response: 
            return False 
        self.info(f"{self.downloader.num_files_downloaded} total files downloaded.\n")
        if self.downloader.num_files_skipped > 0:
            self.info(f"{self.downloader.num_files_skipped} total skipped files, not downloaded.")  
        end = time.time()
        elapsed = end - start
        self.migration_elapsed_time_seconds = self.format_elapsed_time_seconds(elapsed)
        return True 

    def scan_source(self):
        return self.downloader.

def clear_logs(assistant: MigrationAssistant = None):
    print('Clearing logs')
    if assistant:
        assistant.shutdown_logging()
        assistant.uploader.shutdown_logging()
        assistant.downloader.shutdown_logging() 
    try:
        shutil.rmtree(LOG_FOLDER_PATH, ignore_errors=True)
    except Exception as e:
        print(f'Failed to remove log directory {LOG_FOLDER_PATH}')
        print(e)
    time.sleep(1)