import os
import time
from pathlib import PurePath  
from concurrent.futures import ThreadPoolExecutor, wait
from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.sharepoint.client_context import ClientContext  
from .constants import SHAREPOINT_APP_CLIENT_ID, SHAREPOINT_APP_CLIENT_SECRET, MAX_UPLOAD_THREADS
from .base import BaseLogging

class SharePointUploader(BaseLogging): 
    def __init__(self, 
        local_folder_base_path: str = '', 
        target_sharepoint_site_url: str = '', 
        target_document_library_name: str = '', 
        target_base_folder: str = '',
        use_multithreading: bool = False,
        verbose : bool = False, 
        name: str = 'SPUploader'): 
        """ Args:
        local_folder_base_path: string, e.g. /Users/username/folderDownloadedFromGoogle
        target_sharepoint_site_url: string, e.g.https://cofc.sharepoint.com/sites/EAMNE
        target_document_library_name: string, e.g. MyDocumentLibrary (no spaces. pull this from URL when looking at Document Library)
        target_base_folder: string; can be empty; provide this if you want to upload all content into a folder inside of the target document library 
        """
        super().__init__(name=name, verbose=verbose)
        self.use_multithreading = use_multithreading
        self.num_completed_uploads = 0
        self.local_folder_base_path = local_folder_base_path
        self.local_folder_base_path_index = len(PurePath(self.local_folder_base_path).parts) - 1
        self.target_site_url = target_sharepoint_site_url
        self.target_document_library_name = target_document_library_name 
        self.target_base_folder = target_base_folder
        self.relative_base = f'{self.target_document_library_name}/{self.target_base_folder}' if \
            target_base_folder else self.target_document_library_name
        self._num_active_uploads = 0 
        self.setup_session()
    
    def configure(self, 
        local_folder_base_path=None, 
        target_sharepoint_site_url=None, 
        target_document_library_name=None, 
        target_base_folder=None,
        use_multithreading=False 
    ):
        """ allow reconfiguration of existing uploader objects """
        self.use_multithreading = use_multithreading
        self.num_completed_uploads = 0 
        self.local_folder_base_path = local_folder_base_path
        self.local_folder_base_path_index = len(PurePath(self.local_folder_base_path).parts) - 1
        self.target_site_url = target_sharepoint_site_url
        self.target_document_library_name = target_document_library_name 
        self.target_base_folder = target_base_folder
        self.relative_base = f'{self.target_document_library_name}/{self.target_base_folder}' if \
            target_base_folder else self.target_document_library_name
        self._num_active_uploads = 0 
        self.setup_session()

    def setup_session(self):
        """ Set up an authenticated sharepoint session to enable file uploading
        to target sharepoint site """
        self.info("Setting up authenticated SharePoint session")   
        auth_context = AuthenticationContext('https://cofc.sharepoint.com/')
        auth_context.acquire_token_for_app(
            client_id=SHAREPOINT_APP_CLIENT_ID, 
            client_secret=SHAREPOINT_APP_CLIENT_SECRET
        )
        self.context = ClientContext(self.target_site_url, auth_context)
        self.context.load(self.context.web)
        self.context.execute_query() 
        self.info("session ready")

    def set_todo_count(self, total_files_to_upload: int = 0):
        self.total_files_to_upload =  total_files_to_upload
   
    def create_sharepoint_folder(self, folder_path: str):
        """
        Creates a folder in the sharepoint site. return server-relative path to generated folder.  
        Can be multiple levels. Format as dir_path="dir1/dir2/dir3/newDir"
        Such that relative_url becomes relative_base/dir1/dir2/dir3/newDir
        """  
        path_to_folder_from_local_base = os.path.join(
            *PurePath(folder_path).parts[self.local_folder_base_path_index:]) 
        relative_url = f'{self.relative_base}/{path_to_folder_from_local_base}'   
        try:
            self.info(f'Creating sharepoint folder: {relative_url}') 
            f = self.context.web.folders.add(relative_url).execute_query() 
            self.info(f"Create folder successful: {relative_url}")
        except Exception as e: 
            self.error(e)   
            self.error(f'Failed to create folder: {relative_url}. Attempting ancestor tree creation fix.') 
            _split = relative_url.split('/')
            ancestor_inclusive_list = ['/'.join(_split[:i]) for i in range(2, len(_split))]
            for ancestor in ancestor_inclusive_list:
                try:
                    self.context.web.folders.add(ancestor).execute_query()  
                    self.info(f"Create ancestor folder successful: {ancestor}")
                except Exception as e:
                    self.error(e) 
                    self.error(f"Create ancestor folder failed: {ancestor}")
            
            self.info(f'Retrying folder creation: {relative_url}')
            self.create_sharepoint_folder(folder_path=folder_path)   
    
    def get_progress(self):  
        return f'{round(self.num_completed_uploads / self.total_files_to_upload, 2) * 100 }%'

    def _multithreaded_upload(self, folder_path):  
        with ThreadPoolExecutor(max_workers=MAX_UPLOAD_THREADS) as executor:
            folder_futures = {}
            file_futures = {}
            for f in os.listdir(folder_path):
                _full = os.path.join(folder_path, f)  
                if os.path.isdir(_full):
                    folder_futures[executor.submit(self._upload_folder_and_contents, _full)] = _full 
                elif os.path.isfile(_full):
                    file_futures[executor.submit(self._upload_file, _full)] = _full
            for complete_file_upload in wait(file_futures).done:
                self.info(f'Completed file upload: {file_futures[complete_file_upload]}')
            for complete_folder_upload in wait(folder_futures).done:
                self.info(f'Completed recursive folder upload: {folder_futures[complete_folder_upload]}')
             

    def _singlethreaded_upload(self, folder_path):  
        for f in os.listdir(folder_path):
            _full = os.path.join(folder_path, f) 
            if os.path.isdir(_full):
                self._upload_folder_and_contents(_full)  
            elif os.path.isfile(_full):
                self._upload_file(_full)
 
    def _upload_file(self, file_path=None):
        """ Given a path to a downloaded file, upload that file to the target 
        folder on the target site """ 
        self._num_active_uploads += 1
        file_name = self.get_name_of_folder_or_file_from_path(file_path)    
        path_to_file_parent_folder_from_local_base = os.path.join(
                *PurePath(file_path).parts[self.local_folder_base_path_index:-1]) 
        relative_parent_folder_url = f'{self.relative_base}/{path_to_file_parent_folder_from_local_base}' 
        try:   
            self.info(f'Uploading file: {relative_parent_folder_url}/{file_name}') 
            target_folder = self.context.web.get_folder_by_server_relative_url(relative_parent_folder_url)
            with open(file_path, 'rb') as f:
                content = f.read()
                target_folder.upload_file(file_name, content).execute_query()
            self.info(f"Upload successful: {file_name}")
        except Exception as e:
            self.error(f"Failed to upload file: {file_name}")
            self.error(e)
        self._num_active_uploads -= 1
        self.num_completed_uploads += 1  
        self.info(f'Upload Progress: {self.get_progress()}')

    def _upload_folder_and_contents(self, folder_path): 
        """ Create the local folder on sharepoint target and also 
        upload all of the contents """ 
        self._num_active_uploads += 1
        self.create_sharepoint_folder(folder_path)
        if self.use_multithreading:
            self._multithreaded_upload(folder_path)
        else: 
            self._singlethreaded_upload(folder_path)
        self.num_completed_uploads += 1
        self._num_active_uploads -= 1
        self.info(f'Upload Progress: {self.get_progress()}') 
         
    def count_remote_files_recursively(self, folder=None):  
        if not folder:
            folder = self.context.web.get_folder_by_server_relative_url(self.relative_base).get().execute_query()
        self.info(f'Counting files recursively in folder: {folder.name}')
        folders = folder.folders.get().execute_query()  
        files = folder.files.get().execute_query()   
        self.debug(f'Direct child files in {folder.name}: [{", ".join([f.name for f in files])}]') 
        self.debug(f'Direct child folders in {folder.name}: [{", ".join([f.name for f in folders])}]')
        count =  len(files) + sum([self.count_remote_files_recursively(f) for f in folders])
        self.info(f'recursive count from {folder.name}: {count}')
        return count 

    def upload(self, local_folder_base_path: str = ''): 
        # reset for progress tracking
        self.num_completed_uploads = 0
        if os.path.isdir(local_folder_base_path):
            self.debug(f'Beginning upload of local temp folder: \n {self.get_directory_tree(local_folder_base_path)}')
            self._upload_folder_and_contents(local_folder_base_path)   
        while self._num_active_uploads > 0:  
            time.sleep(5)
        self.info("All enqueued upload tasks complete. Upload finished.")
 
if __name__ == '__main__': 
    local_folder= os.path.join(os.path.dirname(__file__), 'huntaj-onedrive-upload-test')
    uploader = SharePointUploader(
        local_folder_base_path=local_folder,
        target_sharepoint_site_url='https://cofc-my.sharepoint.com/personal/huntaj_cofc_edu',
        target_document_library_name='',
        target_base_folder='',
        verbose=True 
    ) 
    uploader.upload(local_folder_base_path=local_folder)