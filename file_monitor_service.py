"""
File System Monitoring Service for Automatic Document Re-processing
Watches local files and folders for changes and triggers re-processing
"""

import os
import hashlib
import asyncio
import logging
from pathlib import Path
from typing import Dict, Set, Optional, Any
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from document_processor import document_processor
from redis_client import redis_store

logger = logging.getLogger(__name__)

class DocumentFileHandler(FileSystemEventHandler):
    """Handle file system events for document files"""
    
    def __init__(self, file_monitor):
        self.file_monitor = file_monitor
        self.supported_extensions = {'.pdf', '.docx', '.txt', '.md', '.doc'}
        
    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory and self._is_supported_file(event.src_path):
            asyncio.create_task(self.file_monitor.handle_file_change(event.src_path, 'modified'))
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory and self._is_supported_file(event.src_path):
            asyncio.create_task(self.file_monitor.handle_file_change(event.src_path, 'created'))
    
    def on_deleted(self, event):
        """Handle file deletion events"""
        if not event.is_directory and self._is_supported_file(event.src_path):
            asyncio.create_task(self.file_monitor.handle_file_deletion(event.src_path))
    
    def on_moved(self, event):
        """Handle file move/rename events"""
        if not event.is_directory:
            if self._is_supported_file(event.src_path):
                asyncio.create_task(self.file_monitor.handle_file_deletion(event.src_path))
            if self._is_supported_file(event.dest_path):
                asyncio.create_task(self.file_monitor.handle_file_change(event.dest_path, 'moved'))
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file extension is supported"""
        return Path(file_path).suffix.lower() in self.supported_extensions

class FileMonitorService:
    """Service for monitoring file changes and triggering re-processing"""
    
    def __init__(self):
        self.observers: Dict[str, Observer] = {}
        self.file_hashes: Dict[str, str] = {}
        self.file_to_doc_mapping: Dict[str, str] = {}
        self.processing_lock = asyncio.Lock()
        
    def start_monitoring(self, directory: str) -> bool:
        """Start monitoring a directory for file changes"""
        try:
            if directory in self.observers:
                logger.info(f"Already monitoring directory: {directory}")
                return True
                
            if not os.path.exists(directory):
                logger.error(f"Directory does not exist: {directory}")
                return False
            
            # Create observer and event handler
            observer = Observer()
            event_handler = DocumentFileHandler(self)
            
            # Start monitoring
            observer.schedule(event_handler, directory, recursive=True)
            observer.start()
            
            self.observers[directory] = observer
            
            # Build initial file hash map
            self._build_initial_file_map(directory)
            
            logger.info(f"Started monitoring directory: {directory}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting file monitoring for {directory}: {str(e)}")
            return False
    
    def stop_monitoring(self, directory: str) -> bool:
        """Stop monitoring a directory"""
        try:
            if directory not in self.observers:
                logger.warning(f"Not monitoring directory: {directory}")
                return False
            
            observer = self.observers[directory]
            observer.stop()
            observer.join()
            
            del self.observers[directory]
            
            logger.info(f"Stopped monitoring directory: {directory}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping file monitoring for {directory}: {str(e)}")
            return False
    
    def stop_all_monitoring(self):
        """Stop all file monitoring"""
        for directory in list(self.observers.keys()):
            self.stop_monitoring(directory)
    
    async def handle_file_change(self, file_path: str, change_type: str):
        """Handle file creation or modification"""
        async with self.processing_lock:
            try:
                logger.info(f"File {change_type}: {file_path}")
                
                # Check if file content actually changed
                current_hash = self._calculate_file_hash(file_path)
                stored_hash = self.file_hashes.get(file_path)
                
                if current_hash == stored_hash:
                    logger.info(f"File content unchanged, skipping: {file_path}")
                    return
                
                # Update hash
                self.file_hashes[file_path] = current_hash
                
                # Check if we already have this file processed
                existing_doc_id = self.file_to_doc_mapping.get(file_path)
                
                if existing_doc_id:
                    logger.info(f"Re-processing existing document: {existing_doc_id}")
                    # Remove old chunks
                    await self._remove_document_chunks(existing_doc_id)
                
                # Process the file
                doc_id = await document_processor.process_file(file_path)
                
                # Store mapping
                self.file_to_doc_mapping[file_path] = doc_id
                
                # Store file metadata in Redis
                self._store_file_metadata(file_path, doc_id, change_type)
                
                logger.info(f"Successfully processed file: {file_path} -> {doc_id}")
                
            except Exception as e:
                logger.error(f"Error processing file change {file_path}: {str(e)}")
    
    async def handle_file_deletion(self, file_path: str):
        """Handle file deletion"""
        async with self.processing_lock:
            try:
                logger.info(f"File deleted: {file_path}")
                
                # Get document ID
                doc_id = self.file_to_doc_mapping.get(file_path)
                
                if doc_id:
                    # Remove chunks from Redis
                    await self._remove_document_chunks(doc_id)
                    
                    # Remove from mappings
                    del self.file_to_doc_mapping[file_path]
                    
                    logger.info(f"Removed document chunks for deleted file: {doc_id}")
                
                # Remove from hash map
                if file_path in self.file_hashes:
                    del self.file_hashes[file_path]
                
            except Exception as e:
                logger.error(f"Error handling file deletion {file_path}: {str(e)}")
    
    def _build_initial_file_map(self, directory: str):
        """Build initial map of files and their hashes"""
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    if Path(file_path).suffix.lower() in {'.pdf', '.docx', '.txt', '.md', '.doc'}:
                        file_hash = self._calculate_file_hash(file_path)
                        self.file_hashes[file_path] = file_hash
            
            logger.info(f"Built initial file map: {len(self.file_hashes)} files")
            
        except Exception as e:
            logger.error(f"Error building initial file map: {str(e)}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file content"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {str(e)}")
            return ""
    
    def _store_file_metadata(self, file_path: str, doc_id: str, change_type: str):
        """Store file metadata in Redis"""
        try:
            file_stats = os.stat(file_path)
            metadata = {
                "doc_id": doc_id,
                "file_path": file_path,
                "filename": os.path.basename(file_path),
                "size": file_stats.st_size,
                "modified_time": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                "created_time": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                "change_type": change_type,
                "processed_at": datetime.now().isoformat(),
                "file_hash": self.file_hashes.get(file_path, "")
            }
            
            # Store in Redis
            mapping_key = f"file_mapping:{doc_id}"
            redis_store.redis_client.hset(mapping_key, mapping=metadata)
            
            logger.info(f"Stored file metadata: {file_path} -> {doc_id}")
            
        except Exception as e:
            logger.error(f"Error storing file metadata: {str(e)}")
    
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
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "monitored_directories": list(self.observers.keys()),
            "total_files_tracked": len(self.file_hashes),
            "processed_documents": len(self.file_to_doc_mapping),
            "active_observers": len(self.observers)
        }

# Global file monitor service instance
file_monitor_service = FileMonitorService() 