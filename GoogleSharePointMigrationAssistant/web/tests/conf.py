TARGET_EXAMPLE = {
    'type': 'sharepoint_folder',
    'details': {
        'site': {
            "createdDateTime": "2022-03-03T16:00:01Z",
            "description": "Lorem ipsum",
            "id": "org.sharepoint.com,longid,longid",
            "lastModifiedDateTime": "2022-11-21T19:44:05Z",
            "name": "this-is-the-site-name",
            "webUrl": "https://org.sharepoint.com/sites/this-is-the-site-name",
            "displayName": "SharePoint Online Site Display Name",
            "root": {},
            "siteCollection": {
                "hostname": "org.sharepoint.com"
            }
        },
        'document_library': {
            "createdDateTime": "2022-11-04T15:48:08Z",
            "description": "My Test Doc Lib",
            "id": "document-library-guid",
            "lastModifiedDateTime": "2022-11-04T17:48:32Z",
            "name": "My Test Doc Lib",
            "webUrl": "https://org.sharepoint.com/sites/this-is-the-site-name/My%20Test%20Doc%20Lib",
            "driveType": "documentLibrary",
            "createdBy": {
                "user": {
                    "email": "username@organization.edu",
                    "id": "user-guid-here",
                    "displayName": "full name of user"
                }
            },
            "lastModifiedBy": {
                "user": {
                    "email": "username@organization.edu",
                    "id": "user-guid-here",
                    "displayName": "full name of user"
                }
            },
            "owner": {
                "group": {
                    "email": "this-is-the-site-name@org.onmicrosoft.com",
                    "id": "group guid",
                    "displayName": "this-is-the-site-name Owners"
                }
            },
            "quota": {}
        },
        'folder': {
            "createdDateTime": "2022-11-04T15:51:26Z",
            "eTag": "etag value",
            "id": "folder-guid",
            "lastModifiedDateTime": "2022-11-04T15:58:34Z",
            "name": "My Folder 1",
            "webUrl": "https://org.sharepoint.com/sites/this-is-the-site-name/My%20Test%20Doc%20Lib/My%20Folder%201",
            "cTag": "ctag value",
            "size": 20296,
            "createdBy": {
                "user": {
                    "email": "username@organization.edu",
                    "id": "user-guid-here",
                    "displayName": "full name of user"
                }
            },
            "lastModifiedBy": {
                "user": {
                    "email": "username@organization.edu",
                    "id": "user-guid-here",
                    "displayName": "full name of user"
                }
            },
            "parentReference": {
                "driveType": "documentLibrary",
                "driveId": "document-library-guid",
                "id": "longidofthisfolder",
                "path": "/drives/document-library-guid/root:"  # it's in the root of the doc lib
            },
            "fileSystemInfo": {
                "createdDateTime": "2022-11-04T15:51:26Z",
                "lastModifiedDateTime": "2022-11-04T15:58:34Z"
            },
            "folder": {
                "childCount": 1
            },
            "shared": {
                "scope": "users"
            }
        }
    }
}

GOOGLE_FOLDER_SOURCE = {
    'type': 'folder',  # alternative is folder
    'details':   {
        "kind": "drive#file",
        "id": "scoobydoobydoo-folder",
        "name": "really cool folder",
        "mimeType": "application/vnd.google-apps.folder"
    }
}
GOOGLE_SHARED_DRIVE_SOURCE = {
    'type': 'shared_drive',  # alternative is folder
    'details':    {
        "id": "scoobydoobydoo-shared-drive",
        "name": "super sick shared drive",
        "kind": "drive#drive"
    }
}
