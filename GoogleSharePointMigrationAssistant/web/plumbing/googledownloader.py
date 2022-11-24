from asyncio import ALL_COMPLETED
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.http import MediaIoBaseDownload, HttpRequest, HttpError 
from google.oauth2.service_account import Credentials as CredentialsSVCAccount
from google.oauth2.credentials import Credentials as CredentialsOauth
from googleapiclient.discovery import build 
from ratelimit import limits, sleep_and_retry 
from sanitize_filename import sanitize
from concurrent.futures import wait, ThreadPoolExecutor
import httplib2
import math
import time 
import shutil 
import os
from ..models import AdministrationSettings, Migration
from .base import BaseLogging
from .constants import (
    GOOGLE_DRIVE_SLEEP_RETRY_SECONDS, 
    MAX_GOOGLE_DRIVE_QUERIES_PER_ONE_HUNDRED_SECONDS,
    ONE_HUNDRED_SECONDS, DEFAULT_PAGESIZE, MAX_DOWNLOAD_THREADS,
    MAX_LIST_THREADS
)

class GoogleToSharePoint(BaseLogging):
    def __init__(self, 
    verbose: bool = False, 
    uploader = None , # sharepoint uploader or onedrive uploader  
    local_temp_dir: str = '',
    file_batch_size: int = 100, 
    name: str = 'GoogleDownloader',
    auth_method: str = 'svc_account', # alternative is 'oauth',
    migration: Migration = None, 
    request: HttpRequest = None,
    ): 
        super().__init__(name=name, verbose=verbose)
        self.admin_config = AdministrationSettings.objects.first()
        self.migration = migration
        self.file_batch_size = file_batch_size
        self.scopes = ['https://www.googleapis.com/auth/drive.readonly'] 
        self.folder_type = 'application/vnd.google-apps.folder'  
        self.uploader = uploader
        self.request = request
        # init 
        self.num_files_already_in_destination = 0
        self.local_temp_dir = os.path.join(os.path.dirname(__file__), local_temp_dir)
        self.info(f'self.local_temp_dir={self.local_temp_dir}')
        self.num_active_downloads = 0 
        self.uploader_running = False 
        self.current_batch_downloaded = 0 
        self.num_files_skipped = 0 
        self.num_files_downloaded = 0 
        self.num_files_failed_to_download = 0 
        self.total_drive_files = 0 
        self.num_active_downloads = 0
        self.setup_service(auth_method=auth_method) 
        self.info({
            'google_downloader__init__': 'initialized successfully'
        })
 

    def _get_google_credentials_from_session(self):
        """ Alternative to service account credentials. Use self.request to pull google creds from session. """
        return CredentialsOauth(**self.request.session.get('google_credentials'))
    
    def _get_google_credentials_from_svc_account_config(self):
        """ Alternative to Oauth session. Use Service account configuration for creating connection."""
        return CredentialsSVCAccount.from_service_account_info(
                self.admin_config.google_service_account_auth_json_credentials, 
                scopes=self.scopes
            )

    def setup_service(self, auth_method: str = 'oauth'):
        if auth_method == 'svc_account': 
            self.creds = self._get_google_credentials_from_svc_account_config()
        elif auth_method == 'oauth':
            self.creds = self._get_google_credentials_from_session()
        try:  
            def build_request(http=None, *args, **kwargs):
                """ 
                Create a new Http() object for every request since  
                httplib2 not threadsafe inherently.  
                """
                new_http = AuthorizedHttp(self.creds, http=httplib2.Http())
                return HttpRequest(new_http, *args, **kwargs) 
            self.build_request = build_request
            authorized_http = AuthorizedHttp(self.creds, http=httplib2.Http())
            self.service = build('drive', 'v3', requestBuilder=build_request, http=authorized_http) 
            self.debug({
                'google_drive_downloader_service': self.service.__dict__
            })
        except Exception as e:
            self.error("Error connecting to Google Drive")
            self.error(e) 

    def file_is_migratable(self, file): 
        """ Determine whether a given file is migratable. 
        Certain mimetypes not migratable to M365 environment. """ 
        non_migratable_mimetypes = [
            'application/vnd.google-apps.form',
            'application/vnd.google-apps.shortcut'
        ]
        migratable = True 
        for mt in non_migratable_mimetypes: 
            if file['mimeType'] == mt: 
                migratable = False 
        return migratable 

    def file_too_large_for_export(self, file): 
        """ return true if file too large for export. 10MB appears to be limit.
        https://stackoverflow.com/questions/44323057/get-file-size-from-google-drive-api-python
        Note: Although if the file is native to Google Drive such as a file made 
        within Google Docs or Sheets those files do not take up space against 
        your quota and thus don't have a size.  
        """
        if 'size' in file:
            file_size_bytes = file['size'] 
            file_size_bytes = int(file['size'])
            return file_size_bytes >= 10000000
        else:
            return True

    def convert_size(self, size_bytes):
        """ Convert size in bytes to size in friendly format. """
        if isinstance(size_bytes, str): 
            size_bytes = int(size_bytes)
        
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return "%s %s" % (s, size_name[i])

    def set_file_batch_size(self, fbs):
        """ Set the file batch size. I.e., how many files to download per batch. 
        With larger files, better to use smaller batch size to not overload 
        local file system (IF USING local file system. Less relevant for S3 intermediate storage)."""

        self.file_batch_size = fbs
        self.info(f'File batch size set to {fbs}')

    @sleep_and_retry
    @limits(calls=MAX_GOOGLE_DRIVE_QUERIES_PER_ONE_HUNDRED_SECONDS, period=ONE_HUNDRED_SECONDS)
    def getlist(self, entity='files', query='', **kwargs):
        """ Get full list of records matching a given query """
        result = None
        npt = ''
        while not npt is None:
            if npt != '': kwargs['pageToken'] = npt
            if entity == 'files':
                _cmd = self.service.files().list(q=query, **kwargs)
            elif entity == 'drives': 
                _cmd = self.service.drives().list(q=query, **kwargs) 
            try:
                entries = _cmd.execute()
                if result is None:
                    result = entries 
                else: 
                    result[entity] += entries[entity]
                npt = entries.get('nextPageToken')
            except HttpError as e:
                self.error(f'Error when getting {entity} list: {e}')
                if e.status_code == 403 and e.reason == "Rate Limit Exceeded": 
                    self.error(
                        f'Rate limit exceeded. Sleeping {GOOGLE_DRIVE_SLEEP_RETRY_SECONDS}'
                        f'seconds and retrying.')
                    time.sleep(GOOGLE_DRIVE_SLEEP_RETRY_SECONDS) 
                    result = self.getlist(entity, query, **kwargs) 
            except TimeoutError as etimeout:
                self.error(
                    f'Timeout error when getting {entity} list: {etimeout}. '
                    f'Sleeping {GOOGLE_DRIVE_SLEEP_RETRY_SECONDS} seconds and retrying.')
                time.sleep(GOOGLE_DRIVE_SLEEP_RETRY_SECONDS)
                result = self.getlist(entity, query, **kwargs)  
        return result  
        

    @sleep_and_retry
    @limits(calls=MAX_GOOGLE_DRIVE_QUERIES_PER_ONE_HUNDRED_SECONDS, period=ONE_HUNDRED_SECONDS)
    def handle_google_suite_filetypes(self,file): 
        """ Need to check for specific google-specific file types. If matched, 
        they need to be converted to their corresponding O365-compatible types. 
        You can do this with export_media(mimetype=...)"""
        valid = True  
        too_large = False
        request = None  
        mimeType = file['mimeType']
        file_id = file['id'] 
        file_name = file['name']  
        self.debug('Exporting Google Suite File:')
        self.debug(f'{file_name}:{mimeType}')
        if mimeType == 'application/vnd.google-apps.form':
            self.debug("Google app Form: {} - cannot be downloaded. Skipping...".format(file_name))
            valid = False
            self.num_files_skipped += 1
        elif mimeType == 'application/vnd.google-apps.shortcut':
            self.debug("Google app Shortcut: {} - cannot be downloaded. Skipping...".format(file_name))
            valid = False
            self.num_files_skipped += 1 
        else: 
            # exportable type. but is it exportable in size?    
            if mimeType == 'application/vnd.google-apps.document':
                if self.file_too_large_for_export(file):  
                    key = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    url = file['exportLinks'][key]
                    request = url  
                    too_large = True 
                else:
                    request = self.service.files().export_media(fileId=file_id, 
                                                    mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') 
            elif mimeType == 'application/vnd.google-apps.spreadsheet':
                if self.file_too_large_for_export(file):  
                    key = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    url = file['exportLinks'][key]
                    request = url  
                    too_large = True  
                else:
                    request = self.service.files().export_media(fileId=file_id, 
                                                    mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') 
            elif mimeType == 'application/vnd.google-apps.presentation':
                if self.file_too_large_for_export(file):   
                    key = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    url = file['exportLinks'][key] 
                    request = url #self.service._http.request(url)
                    too_large = True 
                else:
                    request = self.service.files().export_media(fileId=file_id, 
                                                    mimeType='application/vnd.openxmlformats-officedocument.presentationml.presentation') 
            else: 
                # no way of handling too-large google app files that are not forms, not presentations, not spreadsheets, and not documents. 
                # dont check size. just try exporting as PDF. 
                request = self.service.files().export_media(fileId=file_id,  mimeType='application/pdf') 
        return valid, request, file_name, too_large

    @sleep_and_retry
    @limits(calls=MAX_GOOGLE_DRIVE_QUERIES_PER_ONE_HUNDRED_SECONDS, period=ONE_HUNDRED_SECONDS)
    def download_file(self, file):  
        """ Download a file. Optionally pass in parent folder drive id and parent
         folder local path if file is not in the base target_dir """ 
        valid = True  
        too_large = self.file_too_large_for_export(file)
        request = self.service.files().get_media(fileId=file['id'])
        file_name = file['name']
        if "application/vnd.google-apps" in file['mimeType']:  
            valid, request, file_name, too_large = self.handle_google_suite_filetypes(file)
        if too_large:
            self.info(f'File {file_name} too large for export, using exportLink to download.')
        if valid: 
            self._download_worker(file_name, dest_folder=file['parent_folder_local_path'], request=request, too_large=too_large)  
        return file 
    
    def _upload_and_delete(self):  
        self.debug({'_upload_and_delete': 'beginning upload'})
        self.uploader_running = True 
        while self.num_active_downloads > 0: 
            self.debug({'_upload_and_delete': f"Waiting for ({self.num_active_downloads}) active download threads to finish"})
            time.sleep(3) 
        self.uploader.set_todo_count(total_files_to_upload=self.total_drive_files)
        self.uploader.upload(local_folder_base_path=self.local_temp_dir)
        try: 
            shutil.rmtree(self.local_temp_dir)
        except Exception as e: 
            self.error(e) 
        self.debug({'_upload_and_delete': "batch upload and delete complete"})
        self.current_batch_downloaded = 0 
        self.uploader_running = False   

    def _download_worker(self, file_name, dest_folder, request, too_large):   
        try:  
            self.num_active_downloads += 1
            file_name = sanitize(file_name)
            os.makedirs(dest_folder, exist_ok=True)
            filepath = os.path.join(dest_folder, file_name)
            self.info({'_download_worker': f"Downloading file {file_name} ({self.num_files_downloaded + 1}/{self.total_drive_files})"})   
            with open(filepath, "wb") as wer:
                if not too_large:
                    # request is normal HttpRequest
                    done = False
                    try: 
                        downloader = MediaIoBaseDownload(wer, request)  
                        while done is False:
                            status, done = downloader.next_chunk()
                            if status is not None and (status.total_size is not None and status.resumable_progress is not None):
                                self.info({
                                    '_download_worker': "\rDownload %s (%s/%s): %d%%." % (file_name, self.sizeof_fmt(status.total_size), self.sizeof_fmt(status.resumable_progress), int(status.progress() * 100))})
                             
                    except HttpError as e:
                        self.error({'_download_worker': f'error when downloading; {str(e)}'}) 
                else:
                    # request is URL from exportLinks
                    self.info(
                        {'_download_worker': f'downloading {file_name} from exportLink {request}'}) 
                    authorized_http = AuthorizedHttp(self.creds, http=httplib2.Http()) 
                    def postproc(response, content):
                        return response, content
                    request = self.build_request(http=authorized_http, uri=request, postproc=postproc)
                    _, content = request.execute()
                    wer.write(content)  
                self.num_files_downloaded += 1 
                self.current_batch_downloaded += 1  
        except Exception as e:
            self.error(e)  
            self.num_files_failed_to_download += 1
        self.num_active_downloads -= 1

    def get_children_from_drive(self, drive_id): 
        """ Get children files & folders from drive by drive id """
        folders = self.getlist(
                entity='files', 
                query=f"'{drive_id}' in parents and trashed = false and mimeType='{self.folder_type}'", 
                **{
                    'driveId': drive_id,  
                    'corpora': 'drive', 
                    'supportsAllDrives': True,
                    'supportsTeamDrives': True,
                    'includeTeamDriveItems': True, 
                    'includeItemsFromAllDrives': True, 
                    })['files']
        files = self.getlist(
            entity='files', 
            query=f"'{drive_id}' in parents and trashed = false and mimeType!='{self.folder_type}'", 
            **{
                'driveId': drive_id,  
                'corpora': 'drive', 
                'supportsAllDrives': True,
                'supportsTeamDrives': True,
                'includeTeamDriveItems': True, 
                'includeItemsFromAllDrives': True, 
                'fields': 'files(id,name,kind,size,mimeType,exportLinks)'
                })['files']
        return {'folders': folders, 'files': files}  

    @sleep_and_retry
    @limits(calls=MAX_GOOGLE_DRIVE_QUERIES_PER_ONE_HUNDRED_SECONDS, period=ONE_HUNDRED_SECONDS)
    def count_migratable_files_in_folder(self, folder: dict = {}):
        migratable_file_count = 0
        self.debug(f'Counting migratable files in folder: {folder["name"]}')
        folder['name'] = sanitize(folder['name']) 
        _id = folder['id'] 
        kwargs = {
                'pageSize': DEFAULT_PAGESIZE,    
                'supportsAllDrives': True,
                'supportsTeamDrives': True,
                'includeTeamDriveItems': True, 
                'includeItemsFromAllDrives': True, 
                'fields': 'files(id,name,kind,size,mimeType,exportLinks)'
            }
        files = self.getlist(
            entity='files', 
            query=f"'{_id}' in parents and trashed = false and mimeType != '{self.folder_type}'",
            **kwargs)['files'] 
        folders = self.getlist(
            entity='files', 
            query=f"'{_id}' in parents and trashed = false and mimeType = '{self.folder_type}'",
            **kwargs)['files']   
        folder_counts = [] 
        with ThreadPoolExecutor(max_workers=MAX_LIST_THREADS) as executor:
            futures = [executor.submit(self.count_migratable_files_in_folder, f) for f in folders]
            for future in wait(futures).done:
                folder_counts.append(future.result())
        assert len(folder_counts) == len(folders)
        migratable_file_count = len([f for f in files if self.file_is_migratable(f)]) + sum(folder_counts)  
        return migratable_file_count 
        
    def get_progress(self): 
        """ let progress indicate number of successful downloads out of total drive files.
        rather than including failures as progress. that is, could finish at 89% if 11% failed. 
        """
        r = (self.num_files_downloaded ) / self.total_drive_files
        return f'{round(r,2) * 100}%'   

    def _get_batch_for_download_from_files_list(self, files_list: list = []):   
        """ pops batch_size items from list at a time which prevents infinite loop. """
        batch = []
        self.info(f'getting batch for download from files list of length {len(files_list)}')
        while len(batch) < self.file_batch_size and len(files_list) > 0:
            batch.append(files_list.pop(0))  
        return batch    

    def _confirm(self, entity_type: str = 'shared_drive', entity: dict = {}): 
        if entity_type == 'shared_drive': 
            src_info = ( 
                f'\tType: Shared Drive\n'
                f'\tID: {entity["id"]}\n'
                f'\tName: {entity["name"]}\n'
            )
        elif entity_type == 'folder': 
            owners = ', '.join([f'{o["displayName"]}-{o["emailAddress"]}' for o in entity['owners']])
            src_info = ( 
                f'\tType: Folder\n'
                f'\tID: {entity["id"]}\n'
                f'\tName: {entity["name"]}\n'
                f'\tOwner(s): {owners}\n' 
            )
        response = input(f'\n\nPlease confirm that the following is the correct Google source to migrate (y|N): \n\n{src_info}')
        response = response.strip().lower()
        if response in ['y', 'yes']:
            self.info('You have confirmed the source! Proceeding with migration.')
            time.sleep(2)
            return True 
        else:
            self.info('You did not confirm the source. Cancelling the migration.')
            time.sleep(2)
            return False   

    def get_o365_extension_from_file_mimetype(self, mimeType):   
        ext = ''  
        if "application/vnd.google-apps" in mimeType:
            if 'google-apps.document' in mimeType: 
                ext = '.docx'
            elif 'google-apps.spreadsheet' in mimeType: 
                ext = '.xlsx'
            elif 'google-apps.presentation' in mimeType: 
                ext = '.pptx'
            else: 
                ext = '.pdf'
        return ext 

    def _get_flattened_files_list_in_folder(self, folder: dict = {}, parent_folder_local_path: str = ''): 
        """ Traverse entire recursive hierarchy in folder and build/return a flattened
        list of files within """
        self.info({'_get_flattened_files_list_in_folde': 'collecting files list'}) 
        files_list = []
        folder_name = sanitize(folder['name'])
        new_parent_folder_local_path = os.path.join(parent_folder_local_path, folder_name)
        folder_id = folder['id'] 
        kwargs = {
                'pageSize': DEFAULT_PAGESIZE,    
                'supportsAllDrives': True,
                'supportsTeamDrives': True,
                'includeTeamDriveItems': True, 
                'includeItemsFromAllDrives': True, 
                'fields': 'files(id,name,kind,size,mimeType,exportLinks)'
            } 
        children_files = self.getlist(
            entity='files', 
            query=f"'{folder_id}' in parents and trashed = false and mimeType != '{self.folder_type}'",
            **kwargs)['files']  
        for chfi in children_files:
            if self.file_is_migratable(chfi):
                self.total_drive_files += 1
                chfi['parent_folder_local_path'] = new_parent_folder_local_path
                chfi['name'] = f'{chfi["name"]}{self.get_o365_extension_from_file_mimetype(chfi["mimeType"])}'                   
                files_list.append(chfi)   
        children_folders = self.getlist(
            entity='files', 
            query=f"'{folder_id}' in parents and trashed = false and mimeType = '{self.folder_type}'",
            **kwargs)['files']     
        with ThreadPoolExecutor(max_workers=MAX_LIST_THREADS) as executor: 
            futures = [
                executor.submit(
                    self._get_flattened_files_list_in_folder,
                    f, 
                    new_parent_folder_local_path
                    ) for f in children_folders
                    ] 
            for future in wait(futures).done:
                files_list.extend(future.result()) 
        return files_list 

    def _get_flattened_files_list_in_drive(self, drive_id: str = ''): 
        """ Traverse entire recursive hierarchy in drive and build/return a flattened
        list of files within; similar to get_flattened_files_list_in_folder but starts at the drive level """
        files_list = []
        drive_children = self.get_children_from_drive(drive_id)
        files, folders = drive_children['files'], drive_children['folders']  
        self.debug(
            f'Shared Drive {drive_id} contains {len(files)} '
            f'file children and {len(folders)} folder children'
            )      
        for f in files:
            if self.file_is_migratable(f) and not self._file_already_migrated(f):
                self.total_drive_files += 1
                f['parent_folder_local_path'] =  self.local_temp_dir
                f['name'] = f'{f["name"]}{self.get_o365_extension_from_file_mimetype(f["mimeType"])}' 
                files_list.append(f)  
        with ThreadPoolExecutor(max_workers=MAX_LIST_THREADS) as executor: 
            futures = [
                executor.submit(self._get_flattened_files_list_in_folder, f) for f in folders]   
            for future in wait(futures, return_when=ALL_COMPLETED).done: 
                files_list.extend(future.result()) # extend for one long flat list of files.
        return files_list   
 
    def _file_already_migrated(self, file: dict = {}, target_files_dict: list = []): 
        """ return whether file has already been migrated. if
        it is already migrated then there should be a key in the target files dict with format:
        f'PARENT<{local_folder_base_path}>PARENT--FILENAME<{f["name"]}>FILENAME'
        with the same parent folder local path and the same name. Obviously 
        cannot use IDs for comparison since Google and SPO/OneDrive do not share unique ids. """ 
        already_migrated = False 
        name, parent_folder_local_path = file['name'], file['parent_folder_local_path']
        name = sanitize(name) 
        key = f'PARENT<{parent_folder_local_path}>PARENT--FILENAME<{name}>FILENAME'
        already_migrated = key in target_files_dict 
        if already_migrated:
            self.info(f'{file["name"]} already migrated.')
            self.num_files_already_in_destination += 1 
        return already_migrated

    def _exclude_files_already_migrated_from_source_file_list(self, 
        source_file_list: list = []):  
        """ Do not re-migrate files that are already in the target. 
        Obtain a list of what's in the target. Exclude those from current list
        files to migrate. """
        self.info({'_exclude_files_already_migrated_from_source_file_list': 'Collecting list of files already in target.'})
        target_files_dict = self.uploader.get_flattened_files_dict_in_remote_folder(
            local_folder_base_path=self.local_temp_dir
        ) 
        self.info({'_exclude_files_already_migrated_from_source_file_list': 'already-uploaded files list acquired'})
        return [
            f for f in source_file_list if not self._file_already_migrated(
                file=f, target_files_dict=target_files_dict)
        ]

    def _migrate_files_list(self, flattened_files_list: list = []):
        """ Download a shared drive recursively. """
        self.debug({'_download_files_list': flattened_files_list})
        return self._migrate_files_list_in_batches(
            files_list=flattened_files_list
            )

    def _scan_shared_drive(self):
        """ Scan (do not download/migrate) a shared drive recursively. """
        self.debug({'_scan_shared_drive': self.migration.source_id}) 
        google_files_list = self._get_flattened_files_list_in_drive(drive_id=self.migration.source_id)  
        google_files_list = self._exclude_files_already_migrated_from_source_file_list(
            google_files_list
            )
        return google_files_list

    def _scan_folder(self):
        """ Scan (do not download/migrate) a folder recursively. """
        self.info({'_scan_folder': self.migration.source_id})
        google_files_list = self._get_flattened_files_list_in_folder(
            folder=self.migration.google_source['details'],
            parent_folder_local_path=os.path.dirname(self.local_temp_dir)
            )
        google_files_list = self._exclude_files_already_migrated_from_source_file_list(
            google_files_list
        ) 
        return google_files_list

    def _download_file_batch(self, files_list : list = []):
        self.info({'_download_file_batch': 'starting download threadpool'})
        with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_THREADS) as executor: 
            futures = [executor.submit(self.download_file, f) for f in files_list]
            for fut in wait(futures, return_when=ALL_COMPLETED).done:
                self.info({'_download_file_batch': f'File downloaded: {fut.result()["name"]}'})

    def _migrate_files_list_in_batches(self, files_list: list = []):
        while len(files_list) > 0: 
            self.debug({'_migrate_files_list_in_batches': f'files_still_left,progress={self.get_progress()}'})
            batch = self._get_batch_for_download_from_files_list(
                files_list=files_list
            ) # pops batch_size items from list at a time which prevents infinite loop.
            self.debug({'_migrate_files_list_in_batches': f'collected batch of {len(batch)} files; starting download'})
            self._download_file_batch(batch)
            self.debug({'_migrate_files_list_in_batches': f'batch download complete; starting SharePoint upload'})
            self._upload_and_delete() 
        return True

    def migrate(self, entity_type='shared_drive', entity_name=''):
        if entity_type == 'shared_drive':     
            response = self._download_shared_drive(entity_name=entity_name) 
        elif entity_type == 'folder': 
            response = self._download_folder(entity_name=entity_name)
        return response 

    