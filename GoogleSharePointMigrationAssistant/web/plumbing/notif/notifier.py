import os 
import smtplib 
import ssl  
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from urllib.parse import quote
from django.core.cache import cache 
from ...models import Migration, AdministrationSettings
from ..base import BaseUtil

class Notifier(BaseUtil): 
    def __init__(self, name: str = 'Notifier'):
        super().__init__(
            name=name, 
            verbose=False
            ) 
        config = cache.get('config', AdministrationSettings.objects.first())
        cache.set('config', config)
        self.smtp_username = config.smtp_username
        self.smtp_password = config.smtp_password
        self.smtp_port = config.smtp_port
        self.smtp_server = config.smtp_server
        self.subject = config.smtp_subject if config.smtp_subject else "Google Drive to SharePoint Migration Complete"

    def notify_completion(self, 
        migration: Migration = None, 
        num_files_migrated: int = 0,
        num_files_already_migrated: int = 0,
        total_migratable_drive_files: int = 0,
        total_unmigratable_drive_files: int = 0,
        elapsed_time: str = ''): 
        """ Send an email with information about completed migration to 
        stakeholders stored in the notify_stakeholders property of the migration in the 
        JSON map. """
        self.migration = migration 
        self.num_files_migrated = num_files_migrated
        self.num_files_already_migrated = num_files_already_migrated
        self.total_migratable_drive_files = total_migratable_drive_files 
        self.total_unmigratable_drive_files = total_unmigratable_drive_files 
        self.elapsed_time = elapsed_time 
        self.to_emails = [self.migration.user.email]
        self.info({'notify_completion': {
            'from': self.smtp_username,
            'to': self.to_emails,
        }})
        
        self.files_already_migrated_msg = ''
        if self.num_files_already_migrated > 0:
            self.files_already_migrated_msg = (
                f'{self.num_files_already_migrated} files were already in the '
                f'destination likely as a result of the migration assistant '
                f'running more than once. '
            )

        if self.migration.target_type == 'sharepoint_folder': 
            msg_body = self.get_sharepoint_notification_msg() 
        elif self.migration.target_type ==  'onedrive_folder':
            msg_body = self.get_onedrive_notification_msg() 
        try:
            self.send_notification(msg_body)
        except Exception as e: 
            print(e) 

    def get_onedrive_notification_msg(self): 
        fname = 'notification-onedrive.txt'
        notification_template_file = os.path.join(os.path.dirname(__file__), fname)
        with open(notification_template_file, 'r') as f:
            content = f.read()
        template = Template(content)
        SKIPPED_MESSAGE = "" if self.total_unmigratable_drive_files == 0 else (
            f'{self.total_unmigratable_drive_files} files were skipped due to incompatibility '
            'with the OneDrive environment and the inability to convert to a compatible version.'
        ) 
        msg_body = template.substitute( 
            GOOGLE_SOURCE_NAME=self.migration.source_name,
            GOOGLE_SOURCE_TYPE=self.migration.source_type, 
            NUM_FILES_MIGRATED=self.num_files_migrated, 
            SKIPPED_MESSAGE=SKIPPED_MESSAGE,
            TOTAL_MIGRATABLE_DRIVE_FILES=self.total_migratable_drive_files,  
            ELAPSED_TIME=self.elapsed_time,
            NUM_FILES_ALREADY_MIGRATED_MSG=self.files_already_migrated_msg
        )
        return msg_body

    def get_sharepoint_notification_msg(self): 
        fname = 'notification-sharepoint-site.txt'
        notification_template_file = os.path.join(os.path.dirname(__file__), fname)
        with open(notification_template_file, 'r') as f:
            content = f.read()
        template = Template(content)
        SKIPPED_MESSAGE = "" if self.total_unmigratable_drive_files == 0 else (
            f'{self.total_unmigratable_drive_files} files were skipped due to incompatibility '
            'with the SharePoint environment and the inability to convert to a compatible version.'
        )
        if self.migration.target_folder_name != 'root':
            full_target = (
                f"{self.migration.target_site_url}"
                f"/{quote(self.migration.target_document_library_name)}"
                f"/{quote(self.migration.target_folder_name)}"
            )
        else: 
            full_target = (
                f"{self.migration.target_site_url}"
                f"/{quote(self.migration.target_document_library_name)}"
            )
        msg_body = template.substitute( 
            GOOGLE_SOURCE_NAME=self.migration.source_name,
            GOOGLE_SOURCE_TYPE=self.migration.source_type,
            TARGET_SHAREPOINT_SITE=self.migration.target_site_display_name,
            FULL_DESTINATION_URL=full_target,
            NUM_FILES_MIGRATED=self.num_files_migrated, 
            SKIPPED_MESSAGE=SKIPPED_MESSAGE,
            TOTAL_MIGRATABLE_DRIVE_FILES=self.total_migratable_drive_files,  
            ELAPSED_TIME=self.elapsed_time,
            NUM_FILES_ALREADY_MIGRATED_MSG=self.files_already_migrated_msg
        )
        return msg_body
    
    def send_notification(self, msg_body): 
        """ Send a notifiation to the migration's related user's email. 
        Note: https://stackoverflow.com/questions/59411362/ssl-certificate-verify-failed-certificate-verify-failed-unable-to-get-local-i
        """
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:   
            msg = MIMEMultipart('alternative')
            msg['Subject'] = self.subject
            msg['From'] = self.smtp_username
            msg['To'] = ', '.join(self.to_emails)
            msg.attach(MIMEText(msg_body, 'plain'))  
            server.starttls(context=ssl.create_default_context())
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(
                self.smtp_username,
                self.to_emails,
                msg.as_string()
            )
        self.info({'send_notification': {'status': 'sent', 'subject': self.subject, 'from': self.smtp_username, 'to': self.to_emails}})
        self.debug({'send_notification': {'status': 'sent', 'subject': self.subject, 'from': self.smtp_username, 'to': self.to_emails, 'msg_content': msg.as_string()}})