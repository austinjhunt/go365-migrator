from pathlib import Path 
import os 
import json 
from dotenv import load_dotenv
load_dotenv()

LOG_FOLDER_PATH = os.path.join(os.path.dirname(__file__), 'migration-logs')
DEFAULT_PAGESIZE = 1000 
PARENT_PATH = Path(os.path.realpath(__file__)).parent.absolute()
TOKEN_JSON = os.path.join(PARENT_PATH, 'token.json')
CREDENTIALS_JSON = os.path.join(PARENT_PATH, 'credentials.json')

MAX_LIST_THREADS = 10 
MAX_UPLOAD_THREADS = 30 
MAX_DOWNLOAD_THREADS = 10
FILE_BATCH_SIZE = 100 # num files downloaded at a time before uploading to SPO then deleting 
 

# google drive API rate limits
ONE_HUNDRED_SECONDS = 100
MAX_GOOGLE_DRIVE_QUERIES_PER_ONE_HUNDRED_SECONDS = 20000 
GOOGLE_DRIVE_SLEEP_RETRY_SECONDS = 25

# Graph API rate limits
#  Throttling is done per user per app. The threshold is 10000 requests every 10 minutes.
MAX_GRAPH_REQUESTS_PER_MINUTE = 1000 
ONE_MINUTE = 60 
GRAPH_SLEEP_RETRY_SECONDS = 25

# Onedrive file management 
ONEDRIVE_APP_CLIENT_ID = os.environ.get('ONEDRIVE_APP_CLIENT_ID')
ONEDRIVE_APP_CLIENT_SECRET = os.environ.get('ONEDRIVE_APP_CLIENT_SECRET')
ONEDRIVE_APP_TENANT_ID = os.environ.get('ONEDRIVE_APP_TENANT_ID')

# Non-OneDrive SharePoint App-Only Auth File Management
SHAREPOINT_APP_CLIENT_ID = os.environ.get('SHAREPOINT_APP_CLIENT_ID')
SHAREPOINT_APP_CLIENT_SECRET = os.environ.get('SHAREPOINT_APP_CLIENT_SECRET')

# SMTP 
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
SMTP_PORT = int(os.environ.get('SMTP_PORT'))
SMTP_SERVER = os.environ.get('SMTP_SERVER')  

# Google Auth
try:
    GOOGLE_DRIVE_SVCACCOUNT_AUTH = json.loads(os.environ.get('GOOGLE_DRIVE_SVCACCOUNT_AUTH'))
except:
    pass 
try:
    GOOGLE_DRIVE_OAUTH_CREDS = json.loads(os.environ.get('GOOGLE_DRIVE_OAUTH_CREDS'))
except:
    pass 
