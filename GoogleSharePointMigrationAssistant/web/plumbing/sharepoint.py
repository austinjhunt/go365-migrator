import os
import time
from msal import SerializableTokenCache
from concurrent.futures import ThreadPoolExecutor, wait
import json
from sanitize_filename import sanitize
from django.conf import settings
from .constants import MAX_UPLOAD_THREADS
from .m365_util import get_token_from_cache
from .base import BaseUtil
from ..models import Migration
from .graphutil import GraphUtil

class SharePointUploader(BaseUtil, GraphUtil):
    def __init__(self,
                 migration: Migration = None,
                 m365_token_cache: SerializableTokenCache = None,
                 use_multithreading: bool = False,
                 verbose: bool = False,
                 name: str = 'SPUploader'):

        super().__init__(name=name, verbose=verbose, username=migration.user.username)
        self.migration = migration
        self.m365_token_cache = m365_token_cache
        self.use_multithreading = use_multithreading
        self.num_completed_uploads = 0
        self.set_relative_base()
        self._num_active_uploads = 0
        self._num_failed = 0

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
        self.total_files_to_upload = total_files_to_upload

    def _create_sharepoint_folder(self, folder_path='', parent_id=None):
        """ Given a parent ID and a folder name, create a new folder with that name in the parent """
        folder_name = self.get_name_of_folder_or_file_from_path(folder_path)
        if not parent_id:
            if self.migration.target_folder_id == 'root':
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/root/children'
            else:
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{self.migration.target_folder_id}/children'
        else:
            url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{parent_id}/children'
        return self.graph_post(
            url=url, 
            data=json.dumps({
                'name': folder_name,
                'folder': {},
                '@microsoft.graph.conflictBehavior': 'rename'
            })
        )

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
            folder_name = self.get_name_of_folder_or_file_from_path(
                local_folder_base_path)
            exists, folder = self._child_exists(
                child_name=folder_name, parent_folder_id='root')  # define me
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

    def _child_exists(self, child_name: str = '', parent_folder_id: str = ''):
        """ Determine if a child (by name) of a given parent folder (by id) exists already. Return boolean. """
        self.info(
            f'Checking if child already exists: {child_name} in folder {parent_folder_id}')
        exists = False
        child = None
        try:
            if parent_folder_id == 'root':
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/root/children'
            else:
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{parent_folder_id}/children'
            url = f"{url}?$filter=name eq '{child_name}'"
            response = self.graph_get(url=url)
            if 'value' in response:
                response = response['value']
                if len(response) > 0:
                    child = response[0]
                    exists = True
        except Exception as e:
            self.error({'_child_exists': {'error': str(e), 'child_name': child_name, 'parent_folder_id': parent_folder_id}})
        return exists, child

    def get_children_from_folder_id(self, folder_id: str = ''):
        """ Given a folder id, return its children. If no folder id provided, use root. """
        if not folder_id:
            url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/root/children'
        else:
            url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{folder_id}/children'
     
        result = get_token_from_cache(m365_token_cache=self.m365_token_cache)
        response = self.graph_get(url=url)
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
                    folder_futures[executor.submit(
                        self._upload_folder_and_contents, _full, parent_id)] = _full
                elif os.path.isfile(_full):
                    file_futures[executor.submit(
                        self._upload_file, _full, parent_id)] = _full
            for complete_file_upload in wait(file_futures).done:
                self.info(
                    f'Completed file upload: {file_futures[complete_file_upload]}')
            for complete_folder_upload in wait(folder_futures).done:
                self.info(
                    f'Completed recursive folder upload: {folder_futures[complete_folder_upload]}')

    def _singlethreaded_upload(self, folder_path: str = '', parent_id: str = ''):
        for f in os.listdir(folder_path):
            _full = os.path.join(folder_path, f)
            if os.path.isdir(_full):
                self._upload_folder_and_contents(_full, parent_id)
            elif os.path.isfile(_full):
                self._upload_file(_full, parent_id)

    

    def _create_upload_session(self, file_name: str = '', file_size: int = 0, parent_id: str = ''):
        """ Given the ID of some parent (either root of drive or specific folder/item), 
        create an upload session into that item and return the data describing that upload session """
        if not parent_id:
            if self.migration.target_folder_id == 'root':
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/root:/{file_name}:/createUploadSession'
            else:
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{self.migration.target_folder_id}:/{file_name}:/createUploadSession'
        else:
            url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{parent_id}:/{file_name}:/createUploadSession'
        
        result = get_token_from_cache(m365_token_cache=self.m365_token_cache)
        payload = {
            "item": { 
                "@microsoft.graph.conflictBehavior": "rename",
            }
        }  
        response = self.graph_post(url=url, data=json.dumps(payload))
        return response


    def _upload_file_in_chunks(self, file_path: str = '', parent_id: str = ''):
        file_name = self.get_name_of_folder_or_file_from_path(file_path)
        file_size = os.path.getsize(file_path)
        self.info(f'Uploading file in chunks: {file_name}')
        response = None
        upload_session = self._create_upload_session(
            file_name=file_name,
            file_size=file_size,
            parent_id=parent_id,
        )
        if 'uploadUrl' in upload_session:
            upload_session_url = upload_session['uploadUrl']
        else:
            self.error(
                f'Failed to obtain upload session for file '
                f'{file_name} and folder {parent_id}'
            )
            return response
        result = get_token_from_cache(m365_token_cache=self.m365_token_cache)
        with open(file_path, 'rb') as f:
            # reference: https://stackoverflow.com/questions/56270467/uploading-huge-files-into-onedrive-using-sdk
            chunk_size = 327680
            chunk_number = file_size // chunk_size
            chunk_leftover = file_size - chunk_size * chunk_number
            i = 0
            while True:
                chunk_data = f.read(chunk_size)
                start_index = i * chunk_size
                end_index = start_index + chunk_size
                if not chunk_data:
                    break  # end of file
                if i == chunk_number:
                    end_index = start_index + chunk_leftover

                response = self.graph_put(
                    url=upload_session_url,
                    data=chunk_data,
                    headers={
                        'Authorization': f'Bearer {result["access_token"]}',
                        'Content-Length': f'{chunk_size}',
                        'Content-Range': f'bytes {start_index}-{end_index - 1}/{file_size}' 
                    }
                )
                i += 1
        return response

    def _upload_complete_file(self, file_path: str = '', file_name: str = '', parent_id: str = '', total_file_size: int = 0): 
        """ Upload a complete  file without creating a resumable upload session. """
        if not parent_id:
            if self.migration.target_folder_id == 'root':
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/root:/{file_name}:/content'
            else:
                url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{self.migration.target_folder_id}:/{file_name}:/content'
        else:
            url = f'{settings.GRAPH_API_URL}/sites/{self.migration.target_site_id}/drives/{self.migration.target_document_library_id}/items/{parent_id}:/{file_name}:/content'
        result = get_token_from_cache(m365_token_cache=self.m365_token_cache)
        with open(file_path, 'rb') as f:
            content = f.read() 
            response = self.graph_put(
                url=url, 
                headers={
                    'Authorization': f'Bearer {result["access_token"]}', 
                    'Content-Type': 'text/plain', 
                    'Content-Length': f'{total_file_size}'
                    },
                data=content
            )
            return response


    def _upload_file(self, file_path=None, parent_id: str = ''):
        """ Given a path to a downloaded file, upload that file to the target 
        folder on the target site.
        Referenced documentation for using upload sessions: 
        https://docs.microsoft.com/en-us/onedrive/developer/rest-api/api/driveitem_createuploadsession?view=odsp-graph-online
        """  
        file = None 
        file_name = self.get_name_of_folder_or_file_from_path(file_path) 
        exists, file = self._child_exists(child_name=file_name, parent_folder_id=parent_id)
        if not exists:
            self._num_active_uploads += 1
            try:   
                total_file_size = os.path.getsize(file_path)
                if not self.less_than_4mb(total_file_size):
                    file = self._upload_file_in_chunks(
                        file_path=file_path, parent_id=parent_id)
                else:
                    file = self._upload_complete_file(
                        file_path=file_path, file_name=file_name,
                        parent_id=parent_id, total_file_size=total_file_size)
                    if not file:
                        file = self._upload_file_in_chunks(
                            file_path=file_path, parent_id=parent_id)
                
                self.num_completed_uploads += 1 
            except Exception as e:
                self.error({'_upload_file': {'error': str(e)}})
                self._num_failed += 1
                file = None 
            self._num_active_uploads -= 1   
        else:
            self.error({'_upload_file': {'file_already_exists': f'{file_name} in {parent_id}'}})
            self.num_completed_uploads += 1 # count already exists as complete upload
        self.info({'_upload_file': {'progress': self.get_progress()}})
        return file 

    def _upload_folder_and_contents(self, folder_path: str = '', parent_id: str = ''):
        """ Create the local folder on sharepoint target and also upload all of the contents """
        self._num_active_uploads += 1
        folder = self._create_sharepoint_folder(
            folder_path=folder_path, parent_id=parent_id)
        if self.use_multithreading:
            self._multithreaded_upload(
                folder_path=folder_path, parent_id=folder['id'])
        else:
            self._singlethreaded_upload(
                folder_path=folder_path, parent_id=folder['id'])
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
            self.debug(
                f'Beginning upload of local temp folder: \n {self.get_directory_tree(local_folder_base_path)}')
            self._upload_folder_and_contents(
                folder_path=local_folder_base_path
            )
        while self._num_active_uploads > 0:
            time.sleep(5)
        self.info("All enqueued upload tasks complete. Upload finished.")
