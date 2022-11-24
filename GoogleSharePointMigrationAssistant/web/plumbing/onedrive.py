import msal 
import os  
import time 
from ratelimit import sleep_and_retry, limits
import requests
import json  
from urllib3.exceptions import ProtocolError
from concurrent.futures import wait, ThreadPoolExecutor 
from sanitize_filename import sanitize  
from .constants import (
    ONEDRIVE_APP_CLIENT_ID, ONEDRIVE_APP_CLIENT_SECRET, 
    ONEDRIVE_APP_TENANT_ID, MAX_UPLOAD_THREADS, 
    MAX_GRAPH_REQUESTS_PER_MINUTE, ONE_MINUTE,
    GRAPH_SLEEP_RETRY_SECONDS, GRAPH_API_BASE
)
from .base import BaseUtil

class OneDriveUploader(BaseUtil):
    def __init__(self, 
        name: str = 'OneDriveUploader', 
        local_folder_base_path: str = '',
        verbose: bool = False,
        username: str = ''):
        super().__init__(name, verbose) 
        self.username = username
        self.local_folder_base_path = local_folder_base_path
        self._num_failed = 0
        self.already_migrated_map = {}
        self.num_completed_uploads = 0
        self._num_active_uploads = 0     
        self.base_folder_id = None # updated when uploading base folder 
        self.session = requests.Session()
       
        self.scopes = [
            "https://graph.microsoft.com/.default", 
            "offline_access"
        ]
        self.update_auth_token()


    def update_auth_token(self):
        """   
        Refresh tokens are not available when using the implicit grant 
        and are unnecessary when using the client_credentials grant. 
        When using client_credentials (as we are here) 
        there isn't a user authenticated and therefore there isn't 
        a need to "refresh" a token since you can simply request 
        a new token when needed.

        Reference: https://stackoverflow.com/questions/47588820/microsoft-graph-api-not-returning-refresh-token
        """
        self.info('Refreshing auth token')
        token = self.acquire_token()
        access_token = token['access_token']
        self.session.headers.update(
            {'Authorization': f'Bearer {access_token}'}
        )  
        self.info('Auth token refreshed')

    @sleep_and_retry
    @limits(calls=MAX_GRAPH_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
    def acquire_token(self):  
        self.info('Acquiring token for Graph API communication')
        authority_url = f'https://login.microsoftonline.com/{ONEDRIVE_APP_TENANT_ID}'
        self.app = msal.ConfidentialClientApplication(
            authority=authority_url,
            client_id=ONEDRIVE_APP_CLIENT_ID, 
            client_credential=ONEDRIVE_APP_CLIENT_SECRET, 
        )    
        return self.app.acquire_token_for_client(scopes=self.scopes)   

    def get_progress(self):   
        return f'{round((self.num_completed_uploads / self.total_files_to_upload), 2) * 100 }%'
    
 
    def create_folder(self, folder_name: str = '', parent_folder_id: str = ''):
        self.info(f'Creating folder {folder_name} in parent folder {parent_folder_id}')
        if parent_folder_id == 'root': 
            url = f'{GRAPH_API_BASE}/users/{self.username}/drive/root/children'
        else:
            url = f'{GRAPH_API_BASE}/users/{self.username}/drive/items/{parent_folder_id}/children' 
        payload = {
            'name': folder_name,
            'folder': {}, 
            "@microsoft.graph.conflictBehavior": "rename"
        }
        self.session.headers.update({'Content-Type': 'application/json'})
        response = self.graph_post(url, data=json.dumps(payload)).json()   
        return response

    @sleep_and_retry
    @limits(calls=MAX_GRAPH_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
    def graph_get(self, url): 
        response = None 
        try:
            response = self.session.get(url)
            json_response = response.json()
            if 'error' in json_response:
                err = json_response['error']
                if 'code' in err:
                    errcode = err['code']
                    if errcode == 'InvalidAuthenticationToken':
                        self.update_auth_token()
                        # reinvoke same request 
                        self.graph_get(url)
        except requests.exceptions.JSONDecodeError as e:
            self.error(f'JSONDecode Error with GET {url}: {e}') 
        except requests.exceptions.ConnectTimeout as etimeout:
            self.error(
                f'Timeout Error with GET {url}: {etimeout}\n'
                f'Retrying after {GRAPH_SLEEP_RETRY_SECONDS} seconds')
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response = self.graph_get(url) 
        except (
            requests.exceptions.ConnectionError,
            # handle Connection aborted, RemoteDisconnected 
            # ref: https://github.com/urllib3/urllib3/issues/1327
            ProtocolError 
            ) as econnerror:
            self.error(f'Connection Error with GET {url}: {econnerror}\n'
            f'Retrying after {GRAPH_SLEEP_RETRY_SECONDS}')
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response = self.graph_get(url)  
        return response 
    
    @sleep_and_retry
    @limits(calls=MAX_GRAPH_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
    def graph_put(self, url, data):  
        response = None 
        try: 
            response = self.session.put(url, data=data) 
            json_response = response.json()
            if 'error' in json_response:
                err = json_response['error']
                if 'code' in err:
                    errcode = err['code']
                    if errcode == 'InvalidAuthenticationToken':
                        self.update_auth_token()
                        # reinvoke same request 
                        self.graph_put(url, data)
        except requests.exceptions.JSONDecodeError as e:
            self.error(f'Error with PUT {url}: {e}') 
        except requests.exceptions.ConnectTimeout as etimeout:
            self.error(
                f'Timeout Error with PUT {url}: {etimeout}\n'
                f'Retrying after {GRAPH_SLEEP_RETRY_SECONDS}')
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response = self.graph_put(url, data)
        except requests.exceptions.ConnectionError as econnerror:
            self.error(
                f'Connection Error with PUT {url}: {econnerror}\n'
                f'Retrying after {GRAPH_SLEEP_RETRY_SECONDS}'
                )
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response = self.graph_put(url, data)
        return response 

    @sleep_and_retry
    @limits(calls=MAX_GRAPH_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
    def graph_post(self, url, data):   
        response = None 
        try:
            response = self.session.post(url, data=data)  
            json_response = response.json()
            if 'error' in json_response:
                err = json_response['error']
                if 'code' in err:
                    errcode = err['code']
                    if errcode == 'InvalidAuthenticationToken':
                        self.update_auth_token()
                        # reinvoke same request 
                        self.graph_post(url, data)
        except requests.exceptions.JSONDecodeError as e:
            self.error(f'Error with POST {url}: {e}')  
        except requests.exceptions.ConnectTimeout as etimeout:
            self.error(
                f'Timeout Error with POST {url}: {etimeout}\n'
                f'Retrying after {GRAPH_SLEEP_RETRY_SECONDS} seconds')
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response = self.graph_post(url, data)
        except requests.exceptions.ConnectionError as econnerror:
            self.error(
                f'Connection Error with POST {url}: {econnerror}\n'
                f'Retrying after {GRAPH_SLEEP_RETRY_SECONDS} seconds')
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response = self.graph_post(url, data)
        return response 
     
    def upload_chunk_data_to_upload_session(self, 
        upload_session: str = '', chunk_data = None ):
        return self.graph_put(url=upload_session, data=chunk_data).json() 
 
    def create_upload_session(self, folder_id: str = '', file_name: str = ''):
        self.info(f'Creating upload session: (file={file_name},folder={folder_id})')
        url = f'{GRAPH_API_BASE}/users/{self.username}/drive/items/{folder_id}:/{file_name}:/createUploadSession'
        payload = {
            "item": { 
                "@microsoft.graph.conflictBehavior": "rename",
                "name": file_name
            }
        }  
        response = self.graph_post(url, data=json.dumps(payload)).json()
        return response

    def _upload_file_in_chunks(self, file_path: str = '', file_name: str = '', remote_parent_folder_id: str = '', total_file_size: int = 1): 
        self.info(f'Uploading file in chunks: {file_name}')
        response = None
        upload_session = self.create_upload_session(
                folder_id=remote_parent_folder_id, 
                file_name=file_name
            )
        if 'uploadUrl' in upload_session:
            upload_session = upload_session['uploadUrl']
        else:
            self.error(
                f'Failed to obtain upload session for file '
                f'{file_name} and folder {remote_parent_folder_id}'
                )
            return response 
        with open(file_path, 'rb') as f:
            # reference: https://stackoverflow.com/questions/56270467/uploading-huge-files-into-onedrive-using-sdk 
            chunk_size = 327680 
            chunk_number = total_file_size // chunk_size 
            chunk_leftover = total_file_size - chunk_size * chunk_number
            i = 0 
            while True: 
                chunk_data = f.read(chunk_size)
                start_index = i * chunk_size 
                end_index = start_index + chunk_size
                if not chunk_data:
                    break # end of file
                if i == chunk_number: 
                    end_index = start_index + chunk_leftover

                #Setting the header with the appropriate chunk data location in the file
                self.session.headers.update({
                    'Content-Length':f'{chunk_size}',
                    'Content-Range': f'bytes {start_index}-{end_index - 1}/{total_file_size}'
                })
                response = self.upload_chunk_data_to_upload_session(
                    upload_session=upload_session,
                    chunk_data=chunk_data
                )
                i += 1
        try:   
            self.session.headers.pop('Content-Length')
            self.session.headers.pop('Content-Range')
        except KeyError as e:
            pass 
        return response 

    def _upload_complete_file(self, file_path: str = '', file_name: str = '', remote_parent_folder_id: str = '', total_file_size: int = 0): 
        self.info(f'Uploading complete file: {file_name}')
        url = f'{GRAPH_API_BASE}/users/{self.username}/drive/items/{remote_parent_folder_id}:/{file_name}:/content'
        self.session.headers.update({'Content-Type': 'multipart/form-data', 'Content-Length': f'{total_file_size}'})  
        with open(file_path, 'rb') as f:
            content = f.read() 
            response = self.graph_put(url, data=content) 
        return response 
    
    def less_than_4mb(self, bytes_size: int = 0): 
        bytes_in_4mb = 1024 * 1024 * 4
        res =  bytes_size < bytes_in_4mb 
        return res 

    def _upload_file_worker(self, file_path=None, remote_parent_folder_id: str = ''):
        """ Given a path to a downloaded file, upload that file to the target 
        folder on the target site.
        Referenced documentation for using upload sessions: 
        https://docs.microsoft.com/en-us/onedrive/developer/rest-api/api/driveitem_createuploadsession?view=odsp-graph-online
        """  
        file = None 
        file_name = self.get_name_of_folder_or_file_from_path(file_path) 
        exists, file = self.child_exists(child_name=file_name, parent_folder_id=remote_parent_folder_id)
        if not exists:
            self._num_active_uploads += 1
            self.info(f'Active uploads incremented: {self._num_active_uploads}')
            try:   
                self.info(f'Uploading file to folder: {file_name} -> {remote_parent_folder_id}')  
                total_file_size = os.path.getsize(file_path)
                if self.less_than_4mb(total_file_size): 
                    file = self._upload_complete_file(
                        file_path=file_path,
                        file_name=file_name,
                        remote_parent_folder_id=remote_parent_folder_id
                    )
                else: 
                    file = self._upload_file_in_chunks(
                        file_path=file_path,
                        file_name=file_name,
                        remote_parent_folder_id=remote_parent_folder_id,
                        total_file_size=total_file_size
                    ) 
                    if file is None: 
                        # try complete file upload if chunked did not work.
                        file = self._upload_complete_file(
                            file_path=file_path,
                            file_name=file_name,
                            remote_parent_folder_id=remote_parent_folder_id
                        ) 
                self.info(f"Upload successful: {file_name}")
                self.num_completed_uploads += 1 
            except Exception as e:
                self.error(f"Failed to upload file: {file_name}")
                self._num_failed += 1
                self.error(e)
                file = None 
            self._num_active_uploads -= 1   
            self.info(f'Active uploads decremented: {self._num_active_uploads}')
            self.info(f'Upload Progress: {self.get_progress()}')   
        else:
            self.info(f'File already exists: {file_name} in {remote_parent_folder_id}')
            self.num_completed_uploads += 1 # count pre-existent as already uploaded
            self.info(f'Upload Progress: {self.get_progress()}')  
        return file 
 
    def child_exists(self, child_name: str = '', parent_folder_id: str = ''): 
        self.info(f'Checking if child already exists: {child_name} in folder {parent_folder_id}')
        exists = False
        child = None
        try:
            if parent_folder_id == 'root': 
                url = f'{GRAPH_API_BASE}/users/{self.username}/drive/root/children'
            else:
                url = f'{GRAPH_API_BASE}/users/{self.username}/drive/items/{parent_folder_id}/children' 
            url = f"{url}?$filter=name eq '{child_name}'" 
            self.session.headers.update({'Content-Type': 'application/json'})
            response = self.graph_get(url).json() 
            if 'value' in response:
                response = response['value']
                if len(response) > 0:
                    child = response[0]
                    exists = True  
        except Exception as e:
            self.error(f'{e}\nFailed to check if child exists: {child_name} in folder {parent_folder_id}') 
        return exists, child

    def _upload_folder_worker(self, folder_path: str = '', remote_parent_folder_id : str = ''): 
        """ Create the local folder on sharepoint target and also 
        upload all of the contents """  
        self._num_active_uploads += 1 
        self.info(f'Active uploads incremented: {self._num_active_uploads}')
        folder_name = self.get_name_of_folder_or_file_from_path(folder_path)
        folder_exists, new_folder = self.child_exists(
            child_name=folder_name, parent_folder_id=remote_parent_folder_id
        )  
        if not folder_exists:
            new_folder = self.create_folder(
                folder_name=self.get_name_of_folder_or_file_from_path(folder_path), 
                parent_folder_id=remote_parent_folder_id
            )  
        if not new_folder:
            self._num_active_uploads -= 1
            self.info(f'Active uploads decremented: {self._num_active_uploads}')
            return None 
        if remote_parent_folder_id == 'root' and new_folder:
            self.base_folder_id = new_folder['id']

        with ThreadPoolExecutor(max_workers=MAX_UPLOAD_THREADS) as executor:
            folder_futures = {}
            file_futures = {}
            for f in os.listdir(folder_path):
                _full = os.path.join(folder_path, f)  
                if os.path.isdir(_full):
                    folder_futures[executor.submit(self._upload_folder_worker, _full, new_folder['id'] )] = _full 
                elif os.path.isfile(_full):
                    file_futures[executor.submit(self._upload_file_worker, _full, new_folder['id'] )] = _full
            for complete_file_upload in wait(file_futures).done:
                self.debug(f'Completed file upload process: {file_futures[complete_file_upload]}')
            for complete_folder_upload in wait(folder_futures).done:
                self.debug(f'Completed recursive folder upload process: {folder_futures[complete_folder_upload]}') 
        self._num_active_uploads -= 1 
        self.info(f'Active uploads decremented: {self._num_active_uploads}')
        return True   
        
    def get_children_from_folder_id(self, folder_id: str = ''): 
        if not folder_id:
            url = f'{GRAPH_API_BASE}/users/{self.username}/drive/root/children'
        else:
            url = f'{GRAPH_API_BASE}/users/{self.username}/drive/items/{folder_id}/children' 
        response = self.graph_get(url).json() 
        if 'value' in response:
            return response['value']
        else:
            return None 

    def count_remote_files_recursively(self, folder_id: str = ''):  
        folder_id = self.base_folder_id if not folder_id else folder_id
        children = self.get_children_from_folder_id(folder_id=folder_id)
        files = [c for c in children if 'file' in c]
        folders = [c for c in children if 'folder' in c]
        return len(files) + sum([self.count_remote_files_recursively(folder_id=f['id']) for f in folders]) 

    def get_flattened_files_dict_in_remote_folder(self, local_folder_base_path: str = '', remote_folder_id: str = ''): 
        """ 
        Use recursion to return a flattned map of all files in the passed folder's
        hierarchy. key = parent_folder_local_path, value = name. 
        A dictionary is 6.6 times faster than a list when we lookup in 100 items.
        When it comes to 10,000,000 items a dictionary lookup can be 585714 times faster than a list lookup.
        * remote folder id is id of drive item
        * local folder base path is the path to where that folder lives 
        locally during local download/upload process
        """ 
        files_dict = {}
        if not remote_folder_id:
            # Base. Remote parent folder is currently root. 
            folder_name = self.get_name_of_folder_or_file_from_path(local_folder_base_path)
            exists, folder = self.child_exists(child_name=folder_name, parent_folder_id='root') 
            if exists:
                self.info(f'Folder {folder_name} already uploaded.')
                remote_folder_id = folder['id']
                self.base_folder_id = remote_folder_id
            else:
                self.info(f'Target folder {folder_name} not yet uploaded.')
                return {}
        children = self.get_children_from_folder_id(folder_id=remote_folder_id)
        files = [c for c in children if 'file' in c] 
        for f in files:
            fname = sanitize(f['name'])  
            key = f'PARENT<{local_folder_base_path}>PARENT--FILENAME<{fname}>FILENAME'
            f['parent_folder_local_path'] = local_folder_base_path
            files_dict[key] = f 
        folders = [c for c in children if 'folder' in c]
        for f in folders:
            f_local_path = os.path.join(local_folder_base_path, f['name'])
            # merge dictionary with subfolder dictionary.
            files_dict = files_dict | self.get_flattened_files_dict_in_remote_folder(
                remote_folder_id=f['id'], local_folder_base_path=f_local_path
            )
        return files_dict
 
    def set_todo_count(self, total_files_to_upload: int = 0):
        self.total_files_to_upload =  total_files_to_upload

    def upload(self, local_folder_base_path: str = ''):
        """ Upload a local folder (by path) to a user's onedrive """  
        self.local_folder_base_path = local_folder_base_path 
        if os.path.isdir(local_folder_base_path):  
            if 'migration-logs' in local_folder_base_path:
                # contain logs within already uploaded folder. 
                remote_parent_folder_id = self.base_folder_id
            else:
                remote_parent_folder_id = 'root' 
            response = self._upload_folder_worker(
                local_folder_base_path, 
                remote_parent_folder_id=remote_parent_folder_id
                )
            if not response:
                self.error('Folder was not uploaded')
        else: 
            self.error(f'{local_folder_base_path} is not a directory')
        while self._num_active_uploads > 0: 
            self.info(f'Waiting for completion of active uploads ({self._num_active_uploads})')
            time.sleep(5)
        self.info("All enqueued upload tasks complete. Upload finished.")
     
if __name__ == "__main__":
    onedrive_uploader = OneDriveUploader(verbose=True, username='pagnottaas@cofc.edu') 
    #count = onedrive_uploader.count_remote_files_recursively(folder_id='01SP4JZNTWL7DKVYMOA5CI2W36OHYU4KOP')
    #print(f'Count={count}') 
    #onedrive_uploader.upload(local_folder_base_path=os.path.join(os.path.dirname(__file__), 'huntaj local'))
    count = onedrive_uploader.count_remote_files_recursively(folder_id='014L6INQOEDWGWRRDL2ZD323VFLIKS6NTM')
    print(f'onedrive count in folder: {count}')