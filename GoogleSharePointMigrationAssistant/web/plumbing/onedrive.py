import os
import time
from msal import SerializableTokenCache
from django.conf import settings
import json
from concurrent.futures import wait, ThreadPoolExecutor
from sanitize_filename import sanitize
from .constants import MAX_UPLOAD_THREADS
from .base import BaseUtil
from .graphutil import GraphUtil
from .m365_util import get_token_from_cache


class OneDriveUploader(BaseUtil, GraphUtil):
    def __init__(self,
                 name: str = 'OneDriveUploader',
                 m365_token_cache: SerializableTokenCache = None,
                 local_folder_base_path: str = '',
                 verbose: bool = False,
                 username: str = ''):
        super().__init__(name, verbose, username=username)

        self.username = username
        self.m365_token_cache = m365_token_cache
        self.local_folder_base_path = local_folder_base_path
        self._num_failed = 0
        self.already_migrated_map = {}
        self.num_completed_uploads = 0
        self._num_active_uploads = 0
        self.base_folder_id = None

    def get_progress(self):
        return f'{round((self.num_completed_uploads / self.total_files_to_upload), 2) * 100 }%'

    def _create_onedrive_folder(self, folder_name: str = '', parent_folder_id: str = ''):

        if parent_folder_id == 'root':
            url = f'{settings.GRAPH_API_URL}/users/{self.username}/drive/root/children'
        else:
            url = f'{settings.GRAPH_API_URL}/users/{self.username}/drive/items/{parent_folder_id}/children'
        payload = {
            'name': folder_name,
            'folder': {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        return self.graph_post(url=url, data=json.dumps(payload))

    def _create_upload_session(self, folder_id: str = '', file_name: str = ''):
        url = f'{settings.GRAPH_API_URL}/users/{self.username}/drive/items/{folder_id}:/{file_name}:/createUploadSession'
        payload = {
            "item": {
                "@microsoft.graph.conflictBehavior": "rename",
                "name": file_name
            }
        }
        response = self.graph_post(url, data=json.dumps(payload)).json()
        return response

    def _upload_file_in_chunks(self, file_path: str = '', file_name: str = '', remote_parent_folder_id: str = '', total_file_size: int = 1):
        self.debug({
            '_'
        })
        response = None
        upload_session = self._create_upload_session(
            folder_id=remote_parent_folder_id,
            file_name=file_name
        )
        if 'uploadUrl' in upload_session:
            upload_session_url = upload_session['uploadUrl']
        else:
            self.error(
                {
                    '_upload_file_in_chunks': {
                        'error': 'failed to obtain upload session',
                        'file_name': file_name,
                        'remote_parent_folder_id': remote_parent_folder_id
                    }
                }
            )
            return response
        token = get_token_from_cache(m365_token_cache=self.m365_token_cache)
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
                    break  # end of file
                if i == chunk_number:
                    end_index = start_index + chunk_leftover
                response = self.graph_put(
                    url=upload_session_url,
                    data=chunk_data,
                    headers={
                        'Authorization': f'Bearer {token["access_token"]}',
                        'Content-Length': f'{chunk_size}',
                        'Content-Range': f'bytes {start_index}-{end_index - 1}/{total_file_size}'
                    }
                )
                i += 1
        return response

    def _upload_complete_file(self, file_path: str = '', file_name: str = '', remote_parent_folder_id: str = '', total_file_size: int = 0):
        url = f'{settings.GRAPH_API_URL}/users/{self.username}/drive/items/{remote_parent_folder_id}:/{file_name}:/content'
        token = get_token_from_cache(m365_token_cache=self.m365_token_cache)
        with open(file_path, 'rb') as f:
            content = f.read()
            response = self.graph_put(
                url=url,
                headers={
                    'Content-Type': 'multipart/form-data',
                    'Content-Length': f'{total_file_size}',
                    'Authorization': f'Bearer {token["access_token"]}'},
                data=content)
        return response

    def _upload_file_worker(self, file_path=None, remote_parent_folder_id: str = ''):
        """ Given a path to a downloaded file, upload that file to the target 
        folder on the target site.
        Referenced documentation for using upload sessions: 
        https://docs.microsoft.com/en-us/onedrive/developer/rest-api/api/driveitem_createuploadsession?view=odsp-graph-online
        """
        file = None
        file_name = self.get_name_of_folder_or_file_from_path(file_path)
        exists, file = self._child_exists(
            child_name=file_name, parent_folder_id=remote_parent_folder_id)
        if not exists:
            self._num_active_uploads += 1
            self.info({
                'active_uploads_incremented': self._num_active_uploads,
                'file_name': file_name,
                'remote_parent_folder_id': remote_parent_folder_id
            })
            try:
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
                self.info({'upload_success': file})
                self.num_completed_uploads += 1
            except Exception as e:
                self.error({'upload_fail': file, 'error': str(e)})
                self._num_failed += 1
                file = None
            self._num_active_uploads -= 1
            self.info({
                'active_uploads_incremented': self._num_active_uploads,
                'file_name': file_name,
                'remote_parent_folder_id': remote_parent_folder_id,
                'progress': self.get_progress()
            })
        else:
            self.num_completed_uploads += 1  # count pre-existent as already uploaded
            self.info(f'Upload Progress: {self.get_progress()}')
            self.info({
                'file_already_exists': {
                    'file_name': file_name,
                    'remote_parent_folder_id': remote_parent_folder_id,
                },
                'progress': self.get_progress()
            })
        return file

    def _child_exists(self, child_name: str = '', parent_folder_id: str = ''):
        exists = False
        child = None
        try:
            if parent_folder_id == 'root':
                url = f'{settings.GRAPH_API_URL}/users/{self.username}/drive/root/children'
            else:
                url = f'{settings.GRAPH_API_URL}/users/{self.username}/drive/items/{parent_folder_id}/children'
            url = f"{url}?$filter=name eq '{child_name}'"
            response = self.graph_get(url)
            if 'value' in response:
                response = response['value']
                if len(response) > 0:
                    child = response[0]
                    exists = True
        except Exception as e:
            self.error({'_child_exists': {'error': 'failed to check if child exists',
                       'child_name': child_name, 'parent_folder_id': parent_folder_id}})
        return exists, child

    def _upload_folder_worker(self, folder_path: str = '', remote_parent_folder_id: str = ''):
        """ Create the local folder on sharepoint target and also 
        upload all of the contents """
        self._num_active_uploads += 1
        self.info({
            '_upload_folder_worker': {
                'active_uploads_incremented': self._num_active_uploads
            }
        })
        folder_name = self.get_name_of_folder_or_file_from_path(folder_path)
        folder_exists, new_folder = self._child_exists(
            child_name=folder_name, parent_folder_id=remote_parent_folder_id
        )
        if not folder_exists:
            new_folder = self._create_onedrive_folder(
                folder_name=self.get_name_of_folder_or_file_from_path(
                    folder_path),
                parent_folder_id=remote_parent_folder_id
            )
        if not new_folder:
            self._num_active_uploads -= 1
            self.info({
                '_upload_folder_worker': {
                    'active_uploads_decremented': self._num_active_uploads,
                    'error': f'failed to create new folder {folder_name}'
                }
            })
            return None
        if remote_parent_folder_id == 'root' and new_folder:
            self.base_folder_id = new_folder['id']
        with ThreadPoolExecutor(max_workers=MAX_UPLOAD_THREADS) as executor:
            folder_futures = {}
            file_futures = {}
            for f in os.listdir(folder_path):
                _full = os.path.join(folder_path, f)
                if os.path.isdir(_full):
                    folder_futures[executor.submit(
                        self._upload_folder_worker, _full, new_folder['id'])] = _full
                elif os.path.isfile(_full):
                    file_futures[executor.submit(
                        self._upload_file_worker, _full, new_folder['id'])] = _full
            for complete_file_upload in wait(file_futures).done:
                self.debug({
                    '_upload_folder_worker': {
                        'file_upload_complete': file_futures[complete_file_upload],
                    }
                })
            for complete_folder_upload in wait(folder_futures).done:
                self.debug({
                    '_upload_folder_worker': {
                        'recursive_folder_upload_complete': folder_futures[complete_folder_upload],
                    }
                })
        self._num_active_uploads -= 1
        self.debug({
            '_upload_folder_worker': {
                'active_uploads_decremented': self._num_active_uploads,
            }
        })
        return True

    def get_children_from_folder_id(self, folder_id: str = ''):
        if not folder_id:
            url = f'{settings.GRAPH_API_URL}/users/{self.username}/drive/root/children'
        else:
            url = f'{settings.GRAPH_API_URL}/users/{self.username}/drive/items/{folder_id}/children'
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
            folder_name = self.get_name_of_folder_or_file_from_path(
                local_folder_base_path)
            exists, folder = self._child_exists(
                child_name=folder_name, parent_folder_id='root')
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
        self.total_files_to_upload = total_files_to_upload

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
                self.error({
                    'upload': {
                        'error': f'folder not uploaded',
                        'local_folder_base_path': local_folder_base_path,
                        'remote_parent_folder_id': remote_parent_folder_id
                    }
                })
        else:
            self.error(f'{local_folder_base_path} is not a directory')
        while self._num_active_uploads > 0:
            self.info({'upload': {'self._num_active_uploads': self._num_active_uploads}})
            time.sleep(5)
        self.info({'upload': {'complete': 'all enqueued upload tasks complete'}})
