"""
Google Drive Webhook Service for Automatic Document Re-processing
Handles real-time notifications when documents change in Google Drive
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException

from config import settings
from document_processor import document_processor
from redis_client import redis_store
from google_drive_service import google_drive_service

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self):
        self.webhook_secret = settings.webhook_secret
        self.processed_notifications = set()  # Prevent duplicate processing
        
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify that the webhook came from Google Drive"""
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True
            
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected_signature}", signature)
    
    async def handle_drive_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Drive change notification"""
        try:
            # Extract notification details
            resource_id = notification_data.get('id')
            resource_uri = notification_data.get('resourceUri')
            change_type = notification_data.get('eventType', 'unknown')
            
            logger.info(f"Received Drive notification: {change_type} for resource {resource_id}")
            
            # Prevent duplicate processing
            notification_key = f"{resource_id}_{change_type}_{notification_data.get('eventTime', '')}"
            if notification_key in self.processed_notifications:
                logger.info(f"Notification already processed: {notification_key}")
                return {"status": "already_processed"}
            
            self.processed_notifications.add(notification_key)
            
            # Handle different change types
            if change_type in ['update', 'create']:
                return await self._handle_document_change(resource_id, resource_uri)
            elif change_type == 'trash':
                return await self._handle_document_deletion(resource_id)
            else:
                logger.info(f"Ignoring change type: {change_type}")
                return {"status": "ignored", "change_type": change_type}
                
        except Exception as e:
            logger.error(f"Error handling Drive notification: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")
    
    async def _handle_document_change(self, resource_id: str, resource_uri: str) -> Dict[str, Any]:
        """Handle document update/creation"""
        try:
            # Check if we're already tracking this document
            existing_doc = redis_store.get_document_by_drive_id(resource_id)
            
            if existing_doc:
                logger.info(f"Document {resource_id} already exists, checking for changes...")
                
                # Download current version and check if content changed
                file_info = await google_drive_service.get_file_info(resource_id)
                if not file_info:
                    logger.error(f"Could not get file info for {resource_id}")
                    return {"status": "error", "message": "File not accessible"}
                
                # Check modification time or version
                current_modified = file_info.get('modifiedTime')
                stored_modified = existing_doc.get('modified_time')
                
                if current_modified == stored_modified:
                    logger.info(f"Document {resource_id} not modified, skipping")
                    return {"status": "no_change"}
                
                # Document changed - remove old version and re-process
                logger.info(f"Document {resource_id} modified, re-processing...")
                await self._remove_document_chunks(existing_doc['doc_id'])
            
            # Process the updated/new document
            result = await self._process_drive_document(resource_id, resource_uri)
            
            return {
                "status": "processed",
                "action": "updated" if existing_doc else "created",
                "document_id": result.get('document_id'),
                "chunks_created": result.get('chunks_created', 0)
            }
            
        except Exception as e:
            logger.error(f"Error processing document change: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_document_deletion(self, resource_id: str) -> Dict[str, Any]:
        """Handle document deletion"""
        try:
            existing_doc = redis_store.get_document_by_drive_id(resource_id)
            if existing_doc:
                await self._remove_document_chunks(existing_doc['doc_id'])
                logger.info(f"Removed document chunks for deleted file {resource_id}")
                return {"status": "deleted", "document_id": existing_doc['doc_id']}
            else:
                logger.info(f"Document {resource_id} not found in our system")
                return {"status": "not_found"}
                
        except Exception as e:
            logger.error(f"Error handling document deletion: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def _process_drive_document(self, resource_id: str, resource_uri: str) -> Dict[str, Any]:
        """Process a Google Drive document"""
        try:
            # Download and process the document
            file_path = await google_drive_service.download_file(resource_id)
            if not file_path:
                raise Exception("Failed to download file")
            
            # Process document and create embeddings
            doc_id = await document_processor.process_file(file_path)
            
            # Store metadata linking Drive ID to our document ID
            metadata = await google_drive_service.get_file_info(resource_id)
            redis_store.store_drive_document_mapping(resource_id, doc_id, metadata)
            
            # Get chunk count
            chunks = redis_store.get_document_chunks(doc_id)
            
            return {
                "document_id": doc_id,
                "chunks_created": len(chunks),
                "drive_id": resource_id
            }
            
        except Exception as e:
            logger.error(f"Error processing Drive document {resource_id}: {str(e)}")
            raise
    
    async def _remove_document_chunks(self, doc_id: str):
        """Remove all chunks for a document"""
        try:
            chunks = redis_store.get_document_chunks(doc_id)
            for chunk in chunks:
                redis_store.delete_chunk(chunk['chunk_id'])
            
            # Remove document metadata
            redis_store.delete_document(doc_id)
            
            logger.info(f"Removed {len(chunks)} chunks for document {doc_id}")
            
        except Exception as e:
            logger.error(f"Error removing document chunks: {str(e)}")
            raise
    
    def setup_drive_webhook(self, folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Setup Google Drive webhook for a folder or entire drive"""
        try:
            if not google_drive_service.is_authenticated():
                return {
                    "status": "error", 
                    "message": "Google Drive authentication required. Please authenticate first at /auth/google/login"
                }
            
            webhook_url = f"{settings.app_base_url}/webhooks/drive"
            
            if folder_id:
                # Set up webhook for specific folder
                result = google_drive_service.watch_folder_changes(
                    folder_id=folder_id,
                    webhook_url=webhook_url,
                    webhook_secret=self.webhook_secret
                )
                
                if result.get("status") == "success":
                    logger.info(f"Successfully set up webhook for folder {folder_id}")
                    return {
                        "status": "success",
                        "webhook_url": webhook_url,
                        "resource_id": f"folder:{folder_id}",
                        "watch_id": result.get('watch_id'),
                        "security_enabled": bool(self.webhook_secret),
                        "expiration": result.get('expiration'),
                        "folder_id": folder_id,
                        "scope": "folder_specific"
                    }
                else:
                    return result
            else:
                # Set up webhook for all changes
                result = google_drive_service.watch_all_changes(
                    webhook_url=webhook_url,
                    webhook_secret=self.webhook_secret
                )
                
                if result.get("status") == "success":
                    logger.info("Successfully set up webhook for all Drive changes")
                    return {
                        "status": "success",
                        "webhook_url": webhook_url,
                        "resource_id": "changes",
                        "watch_id": result.get('watch_id'),
                        "security_enabled": bool(self.webhook_secret),
                        "expiration": result.get('expiration'),
                        "start_page_token": result.get('start_page_token'),
                        "scope": "all_changes"
                    }
                else:
                    return result
            
        except Exception as e:
            logger.error(f"Error setting up Drive webhook: {str(e)}")
            return {"status": "error", "message": str(e)}

# Global webhook service instance
webhook_service = WebhookService() 