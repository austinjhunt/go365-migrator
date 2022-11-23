import shutil   
import time 
import json  
import time   
from .constants import *  
from .sharepoint import SharePointUploader
from .googledownloader import GoogleDownloader
from .onedrive import OneDriveUploader
from .base import BaseLogging 

class MigrationAssistant(BaseLogging):
    def __init__(
        self,
        verbose: bool = False, 
        migration: dict = None, 
        name: str = 'MigrationAssistant',
        ): 
        super().__init__(name=name, verbose=verbose)      

        # parse migration map 
        self.migration = migration
        self.local_temp_dir = migration['local_temp_dir'] 
        self.google_source_name = migration['google_source_name']
        self.google_source_type = migration['google_source_type'] 
        self.notify_stakeholders = migration['notify_stakeholders']
        self.wait_for_confirmation_before_migrating = migration['wait_for_confirmation_before_migrating']
        self.target_type = migration['target_type'] 

        self.migration_elapsed_time_seconds = 0 
        self.file_batch_size = FILE_BATCH_SIZE   

        if self.target_type == 'sharepoint_site':   
            self.target_sharepoint_site = migration['target_sharepoint_site']
            self.target_document_library = migration['target_document_library']
            self.target_folder = migration['target_folder'] 
            self.uploader = SharePointUploader(
                local_folder_base_path=self.local_temp_dir,
                target_sharepoint_site_url=self.target_sharepoint_site,
                target_document_library_name=self.target_document_library,
                target_base_folder=self.target_folder,
                use_multithreading=False,
                verbose=verbose
            ) 
        elif self.target_type == 'onedrive': 
            self.uploader = OneDriveUploader(
                verbose=verbose, 
                local_folder_base_path=self.local_temp_dir,
                username=migration['target_onedrive_username']
            )
            
        self.downloader = GoogleDownloader(
            verbose=verbose, 
            uploader=self.uploader,
            local_temp_dir=self.local_temp_dir,
            file_batch_size=FILE_BATCH_SIZE, 
            wait_for_confirmation_before_migrating=self.wait_for_confirmation_before_migrating
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
        if self.target_type == 'sharepoint_site':
            self.uploader.configure(
                local_folder_base_path=LOG_FOLDER_PATH,
                target_sharepoint_site_url=self.target_sharepoint_site, 
                target_document_library_name=self.target_document_library,
                target_base_folder=f'{self.target_folder}/{self.local_temp_dir.split("/")[-1]}',
                use_multithreading=True
            )
            self.uploader.upload(local_folder_base_path=LOG_FOLDER_PATH) 
        elif self.target_type == 'onedrive': 
            self.uploader.num_completed_uploads = 0 
            self.uploader.upload(
                local_folder_base_path=LOG_FOLDER_PATH
            )  

    def migrate(self):
        start = time.time()
        # possible source types: file, folder, user_drive, shared_drive
        response = self.downloader.download(
            entity_type=self.google_source_type,
            entity_name=self.google_source_name
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

def clear_logs(assistant: Google2SharePointAssistant = None):
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

if __name__ == '__main__': 
    migration_map = None    
    with open('map.json', 'r') as f: 
        migration_map = json.load(f)
    if migration_map:
        for migration in migration_map: 
            clear_logs()
            verbose = False if not 'verbose' in migration else migration['verbose']
            assistant = MigrationAssistant(
                migration=migration, 
                verbose=verbose,
                ) 
            if 'file_batch_size' in migration:
                assistant.set_file_batch_size(migration['file_batch_size'])  
            migration_response = assistant.migrate() 
            if migration_response: 
                assistant.notify_completion()   
            assistant.upload_logs_to_destination()  
            clear_logs(assistant)