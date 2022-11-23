import os 
import smtplib 
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from urllib.parse import quote
import ssl  
from ..base import BaseLogging
from ..constants import (
    SMTP_USERNAME, SMTP_PASSWORD, SMTP_PORT, SMTP_SERVER 
) 

class Notifier(BaseLogging): 
    def __init__(self, name: str = 'Notifier'):
        super().__init__(
            name=name, 
            verbose=False
            ) 
        self.smtp_username = SMTP_USERNAME
        self.smtp_password = SMTP_PASSWORD
        self.smtp_port = SMTP_PORT
        self.smtp_server = SMTP_SERVER 

    def notify_completion(self, 
        migration_info: dict = None,  
        num_files_migrated: int = 0,
        num_files_skipped: int = 0,
        total_drive_files: int = 0,  
        num_files_already_migrated: int = 0,
        elapsed_time: str = ''): 
        """ Send an email with information about completed migration to 
        stakeholders stored in the notify_stakeholders property of the migration in the 
        JSON map. """
        self.migration_info = migration_info
        self.num_files_migrated = num_files_migrated
        self.num_files_already_migrated = num_files_already_migrated
        self.num_files_skipped = num_files_skipped
        self.total_drive_files = total_drive_files 
        self.elapsed_time = elapsed_time 
        if 'cc_emails' in migration_info:
            self.cc_emails = migration_info['cc_emails']
        else: 
            self.cc_emails = [] 
        self.to_emails = [el['email'] for el in migration_info['notify_stakeholders']] 
        self.all_recipients = self.to_emails + self.cc_emails 
        self.info( f'Sending notification from {self.smtp_username} to {self.to_emails} (cc={self.cc_emails})' )
        
        self.files_already_migrated_msg = ''
        if self.num_files_already_migrated > 0:
            self.files_already_migrated_msg = (
                f'{self.num_files_already_migrated} files were already in the '
                f'destination likely as a result of the migration assistant '
                f'running more than once. '
            )

        if migration_info['target_type'] == 'sharepoint_site': 
            msg_body = self.get_sharepoint_notification_msg() 
        elif migration_info['target_type'] == 'onedrive':
            msg_body = self.get_onedrive_notification_msg() 
        try:
            self.send_notification(msg_body)
        except Exception as e: 
            print(e) 

    def get_onedrive_notification_msg(self): 
        fname = 'notification-onedrive.txt'
        notification_template_file = os.path.join(os.path.dirname(__file__), fname)
        self.subject ="Google Drive to OneDrive Migration Complete"
        with open(notification_template_file, 'r') as f:
            content = f.read()
        template = Template(content)
        SKIPPED_MESSAGE = "" if self.num_files_skipped == 0 else (
            f'{self.num_files_skipped} files were skipped due to incompatibility '
            'with the OneDrive environment and the inability to convert to a compatible version.'
        ) 
        msg_body = template.substitute( 
            GOOGLE_SOURCE_NAME=self.migration_info['google_source_name'],
            GOOGLE_SOURCE_TYPE=self.migration_info['google_source_type'], 
            NUM_FILES_MIGRATED=self.num_files_migrated, 
            SKIPPED_MESSAGE=SKIPPED_MESSAGE,
            TOTAL_DRIVE_FILES=self.total_drive_files,  
            ELAPSED_TIME=self.elapsed_time,
            NUM_FILES_ALREADY_MIGRATED_MSG=self.files_already_migrated_msg
        )
        return msg_body

    def get_sharepoint_notification_msg(self): 
        fname = 'notification-sharepoint-site.txt'
        self.subject = "Google Drive to SharePoint Migration Complete"
        notification_template_file = os.path.join(os.path.dirname(__file__), fname)
        with open(notification_template_file, 'r') as f:
            content = f.read()
        template = Template(content)
        SKIPPED_MESSAGE = "" if self.num_files_skipped == 0 else (
            f'{self.num_files_skipped} files were skipped due to incompatibility '
            'with the SharePoint environment and the inability to convert to a compatible version.'
        )
        full_target = (
            f"{self.migration_info['target_sharepoint_site']}"
            f"/{quote(self.migration_info['target_document_library'])}"
            f"/{quote(self.migration_info['target_folder'])}"
        )

        msg_body = template.substitute( 
            GOOGLE_SOURCE_NAME=self.migration_info['google_source_name'],
            GOOGLE_SOURCE_TYPE=self.migration_info['google_source_type'],
            TARGET_SHAREPOINT_SITE=self.migration_info['target_sharepoint_site'],
            FULL_DESTINATION_URL=full_target,
            NUM_FILES_MIGRATED=self.num_files_migrated, 
            SKIPPED_MESSAGE=SKIPPED_MESSAGE,
            TOTAL_DRIVE_FILES=self.total_drive_files,  
            ELAPSED_TIME=self.elapsed_time,
            NUM_FILES_ALREADY_MIGRATED_MSG=self.files_already_migrated_msg
        )
        return msg_body
    
    def send_notification(self, msg_body): 
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:   
            msg = MIMEMultipart('alternative')
            msg['Subject'] = self.subject
            msg['From'] = self.smtp_username
            msg['To'] = ', '.join(self.to_emails)
            msg['Cc'] = ', '.join(self.cc_emails)
            msg.attach(MIMEText(msg_body, 'plain'))  
            server.starttls(context=ssl.create_default_context())
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(
                self.smtp_username,
                self.all_recipients,
                msg.as_string()
            )
        self.info(f'Email sent!')