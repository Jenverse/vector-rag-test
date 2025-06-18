import os
import io
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload
import requests
import logging
from config import settings

logger = logging.getLogger(__name__)


class GoogleDriveService:
    def __init__(self):
        """Initialize Google Drive service."""
        self.scopes = [
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/drive.metadata.readonly'
        ]
        self.credentials = None
        self.service = None
        self.token_file = "token.json"
        self.credentials_file = "credentials.json"
        
    def setup_credentials(self, client_id: str, client_secret: str) -> str:
        """Setup Google Drive credentials and return authorization URL."""
        try:
            # Create credentials info
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.google_redirect_uri]
                }
            }
            
            # Create flow
            flow = Flow.from_client_config(
                client_config, 
                scopes=self.scopes
            )
            flow.redirect_uri = settings.google_redirect_uri
            
            # Get authorization URL
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            # Store flow for later use
            self._flow = flow
            
            logger.info("Generated Google Drive authorization URL")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error setting up Google Drive credentials: {str(e)}")
            raise e
    
    def authenticate_with_code(self, auth_code: str) -> bool:
        """Complete authentication with authorization code."""
        try:
            if not hasattr(self, '_flow'):
                raise ValueError("Must call setup_credentials first")
            
            # Exchange code for token
            self._flow.fetch_token(code=auth_code)
            self.credentials = self._flow.credentials
            
            # Save credentials
            with open(self.token_file, 'w') as token:
                token.write(self.credentials.to_json())
            
            # Initialize service
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            logger.info("Successfully authenticated with Google Drive")
            return True
            
        except Exception as e:
            logger.error(f"Error authenticating with Google Drive: {str(e)}")
            return False
    
    def load_credentials(self) -> bool:
        """Load existing credentials from file."""
        try:
            if os.path.exists(self.token_file):
                self.credentials = Credentials.from_authorized_user_file(
                    self.token_file, self.scopes
                )
                
                # Refresh if expired
                if self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                    
                    # Save refreshed credentials
                    with open(self.token_file, 'w') as token:
                        token.write(self.credentials.to_json())
                
                # Initialize service
                self.service = build('drive', 'v3', credentials=self.credentials)
                
                logger.info("Loaded existing Google Drive credentials")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error loading Google Drive credentials: {str(e)}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        return self.service is not None and self.credentials is not None
    
    def extract_file_id_from_url(self, url: str) -> Optional[str]:
        """Extract Google Drive file ID from URL."""
        try:
            # Handle different Google Drive URL formats
            if '/file/d/' in url:
                # https://drive.google.com/file/d/FILE_ID/view
                return url.split('/file/d/')[1].split('/')[0]
            elif '/folders/' in url:
                # https://drive.google.com/drive/folders/FOLDER_ID
                return url.split('/folders/')[1].split('?')[0]
            elif '/document/d/' in url:
                # https://docs.google.com/document/d/FILE_ID/edit
                return url.split('/document/d/')[1].split('/')[0]
            elif '/spreadsheets/d/' in url:
                # https://docs.google.com/spreadsheets/d/FILE_ID/edit
                return url.split('/spreadsheets/d/')[1].split('/')[0]
            elif '/presentation/d/' in url:
                # https://docs.google.com/presentation/d/FILE_ID/edit
                return url.split('/presentation/d/')[1].split('/')[0]
            elif 'id=' in url:
                # Direct file ID parameter
                return url.split('id=')[1].split('&')[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting file ID from URL {url}: {str(e)}")
            return None
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a Google Drive file."""
        try:
            if not self.is_authenticated():
                logger.error("Not authenticated with Google Drive")
                return None
            
            # Get file metadata
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields='id,name,mimeType,modifiedTime,size,webViewLink,parents'
            ).execute()
            
            logger.info(f"Retrieved metadata for file: {file_metadata.get('name')}")
            return file_metadata
            
        except Exception as e:
            logger.error(f"Error getting file metadata for {file_id}: {str(e)}")
            return None
    
    async def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Async wrapper for get_file_metadata (for webhook service compatibility)."""
        return self.get_file_metadata(file_id)
    
    def list_folders(self) -> List[Dict[str, Any]]:
        """List all folders in Google Drive."""
        try:
            if not self.is_authenticated():
                logger.error("Not authenticated with Google Drive")
                return []
            
            # Query for folders only
            query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            results = self.service.files().list(
                q=query,
                fields='files(id,name,modifiedTime,webViewLink)',
                pageSize=100,
                orderBy='name'
            ).execute()
            
            folders = results.get('files', [])
            
            logger.info(f"Found {len(folders)} folders in Google Drive")
            return folders
            
        except Exception as e:
            logger.error(f"Error listing folders: {str(e)}")
            return []
    
    def watch_folder_changes(self, folder_id: str, webhook_url: str, webhook_secret: Optional[str] = None) -> Dict[str, Any]:
        """Set up webhook to watch for changes in a specific folder."""
        try:
            if not self.is_authenticated():
                raise Exception("Not authenticated with Google Drive")
            
            # Create watch request
            watch_request = {
                'id': f"folder_watch_{folder_id}_{int(time.time())}",
                'type': 'web_hook',
                'address': webhook_url,
                'payload': True,
                'expiration': str(int((time.time() + 86400) * 1000))  # 24 hours from now
            }
            
            if webhook_secret:
                watch_request['token'] = webhook_secret
            
            # Set up watch for the folder
            # Note: Google Drive API doesn't directly watch folders, so we watch for changes
            # and filter by parent folder in the webhook handler
            result = self.service.changes().watch(
                body=watch_request,
                supportsAllDrives=True
            ).execute()
            
            logger.info(f"Successfully set up webhook for folder {folder_id}")
            return {
                "status": "success",
                "watch_id": result.get('id'),
                "resource_id": result.get('resourceId'),
                "expiration": result.get('expiration'),
                "folder_id": folder_id
            }
            
        except Exception as e:
            logger.error(f"Error setting up folder webhook: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def watch_all_changes(self, webhook_url: str, webhook_secret: Optional[str] = None) -> Dict[str, Any]:
        """Set up webhook to watch for all Google Drive changes."""
        try:
            if not self.is_authenticated():
                raise Exception("Not authenticated with Google Drive")
            
            # Get current start page token
            start_page_token = self.service.changes().getStartPageToken().execute()
            
            # Create watch request
            watch_request = {
                'id': f"all_changes_{int(time.time())}",
                'type': 'web_hook',
                'address': webhook_url,
                'payload': True,
                'expiration': str(int((time.time() + 86400) * 1000))  # 24 hours from now
            }
            
            if webhook_secret:
                watch_request['token'] = webhook_secret
            
            # Set up watch for all changes
            result = self.service.changes().watch(
                body=watch_request,
                pageToken=start_page_token.get('startPageToken'),
                supportsAllDrives=True
            ).execute()
            
            logger.info("Successfully set up webhook for all Drive changes")
            return {
                "status": "success",
                "watch_id": result.get('id'),
                "resource_id": result.get('resourceId'),
                "expiration": result.get('expiration'),
                "start_page_token": start_page_token.get('startPageToken')
            }
            
        except Exception as e:
            logger.error(f"Error setting up all changes webhook: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def download_file(self, file_id: str) -> Optional[str]:
        """Async wrapper for download_file_content (for webhook service compatibility)."""
        return self.download_file_content(file_id)
    
    def download_file_content(self, file_id: str) -> Optional[str]:
        """Download file content from Google Drive."""
        try:
            if not self.is_authenticated():
                logger.error("Not authenticated with Google Drive")
                return None
            
            # Get file metadata first
            metadata = self.get_file_metadata(file_id)
            if not metadata:
                return None
            
            mime_type = metadata.get('mimeType', '')
            file_name = metadata.get('name', 'unknown')
            
            logger.info(f"Downloading file: {file_name} ({mime_type})")
            
            # Handle different file types
            if 'google-apps' in mime_type:
                # Google Workspace documents
                if 'document' in mime_type:
                    # Google Docs -> Plain text
                    export_mime = 'text/plain'
                elif 'spreadsheet' in mime_type:
                    # Google Sheets -> CSV
                    export_mime = 'text/csv'
                elif 'presentation' in mime_type:
                    # Google Slides -> Plain text
                    export_mime = 'text/plain'
                else:
                    # Default to PDF for other Google apps
                    export_mime = 'application/pdf'
                
                # Export the file
                request = self.service.files().export_media(
                    fileId=file_id, 
                    mimeType=export_mime
                )
            else:
                # Regular files
                request = self.service.files().get_media(fileId=file_id)
            
            # Download content
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Convert to text
            content = file_io.getvalue()
            
            # Handle binary files vs text files
            try:
                if isinstance(content, bytes):
                    text_content = content.decode('utf-8')
                else:
                    text_content = str(content)
                
                logger.info(f"Downloaded {len(text_content)} characters from {file_name}")
                return text_content
                
            except UnicodeDecodeError:
                # For binary files like PDFs, we'll need to save them first
                temp_file = f"temp_{file_id}.{self._get_file_extension(mime_type)}"
                with open(temp_file, 'wb') as f:
                    f.write(content)
                
                logger.info(f"Saved binary file as {temp_file} for processing")
                return temp_file  # Return path for processing
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {str(e)}")
            return None
    
    def _get_file_extension(self, mime_type: str) -> str:
        """Get file extension based on MIME type."""
        mime_map = {
            'application/pdf': 'pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'text/plain': 'txt',
            'text/markdown': 'md',
            'text/csv': 'csv'
        }
        return mime_map.get(mime_type, 'txt')
    
    def list_folder_files(self, folder_url: str) -> List[Dict[str, Any]]:
        """List files in a Google Drive folder."""
        try:
            folder_id = self.extract_file_id_from_url(folder_url)
            if not folder_id:
                logger.error(f"Could not extract folder ID from URL: {folder_url}")
                return []
            
            if not self.is_authenticated():
                logger.error("Not authenticated with Google Drive")
                return []
            
            # Query for files in the folder
            query = f"'{folder_id}' in parents and trashed=false"
            
            results = self.service.files().list(
                q=query,
                fields='files(id,name,mimeType,modifiedTime,webViewLink)',
                pageSize=100
            ).execute()
            
            files = results.get('files', [])
            
            logger.info(f"Found {len(files)} files in folder")
            return files
            
        except Exception as e:
            logger.error(f"Error listing folder files: {str(e)}")
            return []
    
    def check_file_changes(self, file_id: str, last_known_modified: str) -> bool:
        """Check if file has been modified since last known time."""
        try:
            metadata = self.get_file_metadata(file_id)
            if not metadata:
                return False
            
            current_modified = metadata.get('modifiedTime', '')
            
            # Compare modification times
            if current_modified != last_known_modified:
                logger.info(f"File {file_id} has been modified")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking file changes for {file_id}: {str(e)}")
            return False
    
    def create_change_event(self, doc_id: str, changed_chunk_ids: List[str]) -> Dict[str, Any]:
        """Create a change event object."""
        return {
            "event": "doc_changed",
            "doc_id": doc_id,
            "changed_chunk_ids": changed_chunk_ids,
            "timestamp": time.time()
        }


# Global Google Drive service instance
google_drive_service = GoogleDriveService() 