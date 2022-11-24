import os
import time
import requests
from pathlib import PurePath  
from msal import SerializableTokenCache
from concurrent.futures import ThreadPoolExecutor, wait
import json
# from office365.runtime.auth.authentication_context import AuthenticationContext
# from office365.sharepoint.client_context import ClientContext  
from sanitize_filename import sanitize  
from django.conf import settings 
from .constants import MAX_UPLOAD_THREADS, GRAPH_API_BASE
from .m365_util import get_token_from_cache
from .base import BaseUtil
from ..models import Migration

class SharePointUploader(BaseUtil): 
    def __init__(self, 
        local_folder_base_path: str = '', 
        migration: Migration = None, 
        m365_token_cache: SerializableTokenCache = None,
        use_multithreading: bool = False,
        verbose : bool = False, 
        name: str = 'SPUploader'): 
        super().__init__(name=name, verbose=verbose)
        self.migration = migration 
        self.m365_token_cache = m365_token_cache
        self.use_multithreading = use_multithreading
        self.num_completed_uploads = 0
        self.set_relative_base()
        self._num_active_uploads = 0 

    def set_relative_base(self):
        if self.migration.target_folder_name == 'root':
            self.relative_base = self.migration.target_document_library_name
        else:
            self.relative_base = f'{self.migration.target_document_library_name}/{self.migration.target_folder_name}'

    def configure(self, 
        migration: Migration = None,
        use_multithreading=False 
    ):
        """ allow reconfiguration of existing uploader objects """
        self.migration = migration 
        self.use_multithreading = use_multithreading
        self.num_completed_uploads = 0 
        self.set_relative_base()
        self._num_active_uploads = 0 

    def set_todo_count(self, total_files_to_upload: int = 0):
        self.total_files_to_upload =  total_files_to_upload
    

    def _create_sharepoint_folder(self, folder_path = '', parent_id = None):
        """ Given a parent ID and a folder name, create a new folder with that name in the parent """
        folder_name = self.get_name_of_folder_or_file_from_path(folder_path)
        if not parent_id:
            if self.migration.target_folder_id == 'root':
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/root/children'
            else:
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{self.migration.target_folder_id}/children'
        else:
            url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{parent_id}/children'
        result = get_token_from_cache(cache=self.m365_token_cache)
        response = requests.post(
            url=url,
            headers={'Authorization': f'Bearer {result["access_token"]}'},
            data=json.dumps({
                'name': folder_name,
                'folder': {}, 
                '@microsoft.graph.conflictBehavior': 'rename'
            })
        )
        data = response.json()
        msg = {
            '_create_sharepoint_folder_response': {
                'status_code': response.status_code,
                'data': data
            }
        }
        if response.status_code != 200:
            self.error(msg)
            return None
        else:
            self.debug(msg)
        return data 

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
            exists, folder = self.child_exists(child_name=folder_name, parent_folder_id='root')  # define me
            self.debug({'get_flattened_files_dict_in_remote_folder': {
                    'folder_name': folder_name,
                    'already_in_target': exists,  
                }})
            if exists:
                remote_folder_id = folder['id']
                self.base_folder_id = remote_folder_id
            else:
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

    def child_exists(self, child_name: str = '', parent_folder_id: str = ''): 
        """ Determine if a child (by name) of a given parent folder (by id) exists already. Return boolean. """
        self.info(f'Checking if child already exists: {child_name} in folder {parent_folder_id}')
        exists = False
        child = None
        try:
            if parent_folder_id == 'root': 
                url = f'{self.graph_api_base}/sites/{self.target_site["id"]}/drives/{self.target_document_library["id"]}/root/children'
            else:
                url = f'{self.graph_api_base}/sites/{self.target_site["id"]}/drives/{self.target_document_library["id"]}/items/{parent_folder_id}/children'
            url = f"{url}?$filter=name eq '{child_name}'" 
            result = get_token_from_cache(cache=self.m365_token_cache)
            response = requests.get(
                url=url,
                headers={'Authorization': f'Bearer {result["access_token"]}'}
            ).json()
            if 'value' in response:
                response = response['value']
                if len(response) > 0:
                    child = response[0]
                    exists = True  
        except Exception as e:
            self.error(f'{e}\nFailed to check if child exists: {child_name} in folder {parent_folder_id}') 
        return exists, child

    def get_children_from_folder_id(self, folder_id: str = ''): 
        """ Given a folder id, return its children. If no folder id provided, use root. """
        if not folder_id: 
            url = f'{self.graph_api_base}/sites/{self.target_site["id"]}/drives/{self.target_document_library["id"]}/root/children'
        else:
            url = f'{self.graph_api_base}/sites/{self.target_site["id"]}/drives/{self.target_document_library["id"]}/items/{folder_id}/children'
        result = get_token_from_cache(cache=self.m365_token_cache)
        response = requests.get(
            url=url,
            headers={'Authorization': f'Bearer {result["access_token"]}'},
        ).json()
        if 'value' in response:
            return response['value']
        else:
            return None 
    
    def get_progress(self):  
        return f'{round(self.num_completed_uploads / self.total_files_to_upload, 2) * 100 }%'

    def _multithreaded_upload(self, folder_path: str = '', parent_id: str = ''):  
        with ThreadPoolExecutor(max_workers=MAX_UPLOAD_THREADS) as executor:
            folder_futures = {}
            file_futures = {}
            for f in os.listdir(folder_path):
                _full = os.path.join(folder_path, f)  
                if os.path.isdir(_full):
                    folder_futures[executor.submit(self._upload_folder_and_contents, _full, parent_id)] = _full 
                elif os.path.isfile(_full):
                    file_futures[executor.submit(self._upload_file, _full, parent_id)] = _full
            for complete_file_upload in wait(file_futures).done:
                self.info(f'Completed file upload: {file_futures[complete_file_upload]}')
            for complete_folder_upload in wait(folder_futures).done:
                self.info(f'Completed recursive folder upload: {folder_futures[complete_folder_upload]}')
             

    def _singlethreaded_upload(self, folder_path: str = '', parent_id: str = ''):  
        for f in os.listdir(folder_path):
            _full = os.path.join(folder_path, f) 
            if os.path.isdir(_full):
                self._upload_folder_and_contents(_full, parent_id)  
            elif os.path.isfile(_full):
                self._upload_file(_full, parent_id)
    
    def _create_upload_session(self, file_name: str = '', parent_id: str = ''):
        """ Given the ID of some parent (either root of drive or specific folder/item), 
        create an upload session into that item and return the data describing that upload session """
        if not parent_id:
            if self.migration.target_folder_id == 'root':
                upload_session_url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/root:{file_name}:/createUploadSession'
            else:
                upload_session_url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{self.migration.target_folder_id}:{file_name}:/createUploadSession'
        else:
            upload_session_url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{parent_id}:{file_name}:/createUploadSession'
        result = get_token_from_cache(cache=self.m365_token_cache)
        response = requests.post(
            url=upload_session_url,
            headers={'Authorization': f'Bearer {result["access_token"]}'},
            data=""
        )
        data = response.json()
        msg = {
            '_create_upload_session_response': {
                'status_code': response.status_code,
                'data': data
            }
        }
        if response.status_code != 200:
            self.error(msg)
            return None
        else:
            self.debug(msg)
        return data 

    def _upload_file(self, file_path: str = '', remote_parent_folder_id: str = ''): 
        file_name = self.get_name_of_folder_or_file_from_path(file_path)
        self.info(f'Uploading file in chunks: {file_name}')
        response = None
        upload_session = self._create_upload_session(
                file_name=file_name,
                folder_id=remote_parent_folder_id, 
            )
        if 'uploadUrl' in upload_session:
            upload_session = upload_session['uploadUrl']
        else:
            self.error(
                f'Failed to obtain upload session for file '
                f'{file_name} and folder {remote_parent_folder_id}'
                )
            return response 
        total_file_size = os.path.getsize(file_path)
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



    def _upload_folder_and_contents(self, folder_path: str = '', parent_id: str = ''): 
        """ Create the local folder on sharepoint target and also upload all of the contents """ 
        self._num_active_uploads += 1
        folder = self._create_sharepoint_folder(folder_path=folder_path, parent_id=parent_id)
        if self.use_multithreading:
            self._multithreaded_upload(folder_path=folder_path, parent_id=folder['id'])
        else: 
            self._singlethreaded_upload(folder_path=folder_path, parent_id=folder['id'])
        self.num_completed_uploads += 1
        self._num_active_uploads -= 1
        self.info({
            '_upload_folder_and_contents': {'progress': self.get_progress()}
        }) 

    def count_remote_files_recursively(self, folder_id: str = ''):
        """ given a folder, count its files recursively """    
        children = self.get_children_from_folder_id(folder_id)
        count = 0 
        if children is not None:
            for child in children:
                count += 1 if not 'folder' in child else \
                    self.count_remote_files_recursively(folder_id=child['id'])
        return count 

    def upload(self, local_folder_base_path: str = ''): 
        self.num_completed_uploads = 0
        if os.path.isdir(local_folder_base_path):
            self.debug(f'Beginning upload of local temp folder: \n {self.get_directory_tree(local_folder_base_path)}')
            self._upload_folder_and_contents(
                folder_path=local_folder_base_path
                )   
        while self._num_active_uploads > 0:  
            time.sleep(5)
        self.info("All enqueued upload tasks complete. Upload finished.")
 

 