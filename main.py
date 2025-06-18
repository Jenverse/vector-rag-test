import os
import time
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Import our modules
from config import settings
from redis_client import redis_store
from embedding_service import embedding_service
from document_processor import document_processor
from google_drive_service import google_drive_service
from chat_service import chat_service
from webhook_service import webhook_service
from file_monitor_service import file_monitor_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Redis RAG Chatbot",
    description="A Retrieval-Augmented Generation chatbot using Redis as vector database",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class ChatRequest(BaseModel):
    query: str
    top_k: Optional[int] = None
    use_hybrid_search: Optional[bool] = True
    chat_history: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    query: str
    context_count: int
    model_used: str

class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    chunks_count: int
    message: str

class GoogleDriveRequest(BaseModel):
    url: str

class GoogleAuthRequest(BaseModel):
    client_id: str
    client_secret: str

class HealthResponse(BaseModel):
    status: str
    redis_healthy: bool
    services: Dict[str, str]


# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve a simple web interface."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redis RAG Chatbot</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30px; }
            .section { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
            .chat-section { background-color: #f9f9f9; }
            input[type="text"], textarea, input[type="file"] { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }
            button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
            button:hover { background-color: #0056b3; }
            .response { background-color: #e9ecef; padding: 15px; border-radius: 4px; margin: 10px 0; }
            .sources { background-color: #f8f9fa; padding: 10px; border-left: 4px solid #007bff; margin: 10px 0; }
            .error { background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 4px; }
            .success { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Redis RAG Chatbot</h1>
                <p>Upload documents and chat with your knowledge base</p>
            </div>

            <!-- Document Upload Section -->
            <div class="section">
                <h2>📄 Upload Documents</h2>
                <input type="file" id="fileInput" multiple accept=".pdf,.docx,.md,.txt">
                <button onclick="uploadFile()">Upload Files</button>
                <div id="uploadResult"></div>
            </div>

            <!-- Google Drive Section -->
            <div class="section">
                <h2>🗂️ Google Drive Integration</h2>
                <input type="text" id="driveUrl" placeholder="Paste Google Drive file or folder URL">
                <button onclick="processDriveUrl()">Process Drive Content</button>
                <div id="driveResult"></div>
            </div>

            <!-- Webhook Setup Section -->
            <div class="section">
                <h2>🔔 Webhook Setup</h2>
                <p>Set up automatic processing when Google Drive files change</p>
                <input type="text" id="folderId" placeholder="Google Drive Folder ID (optional - leave empty for all files)">
                <button onclick="setupWebhook()">Setup Folder Webhook</button>
                <div id="webhookResult"></div>
            </div>

            <!-- Chat Section -->
            <div class="section chat-section">
                <h2>💬 Chat with Your Documents</h2>
                <textarea id="chatQuery" rows="3" placeholder="Ask a question about your documents..."></textarea>
                <button onclick="sendQuery()">Send Query</button>
                <div id="chatResult"></div>
            </div>

            <!-- Health Check -->
            <div class="section">
                <h2>🏥 System Health</h2>
                <button onclick="checkHealth()">Check System Health</button>
                <div id="healthResult"></div>
            </div>
        </div>

        <script>
            async function uploadFile() {
                const fileInput = document.getElementById('fileInput');
                const resultDiv = document.getElementById('uploadResult');
                
                if (fileInput.files.length === 0) {
                    resultDiv.innerHTML = '<div class="error">Please select files to upload</div>';
                    return;
                }

                const formData = new FormData();
                for (let i = 0; i < fileInput.files.length; i++) {
                    formData.append('files', fileInput.files[i]);
                }

                try {
                    resultDiv.innerHTML = '<div>Uploading and processing files...</div>';
                    const response = await fetch('/upload-documents', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        resultDiv.innerHTML = `<div class="success">Successfully processed ${data.length} files</div>`;
                    } else {
                        resultDiv.innerHTML = `<div class="error">Error: ${data.detail}</div>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }

            async function processDriveUrl() {
                const url = document.getElementById('driveUrl').value;
                const resultDiv = document.getElementById('driveResult');
                
                if (!url) {
                    resultDiv.innerHTML = '<div class="error">Please enter a Google Drive URL</div>';
                    return;
                }

                try {
                    resultDiv.innerHTML = '<div>Processing Google Drive content...</div>';
                    const response = await fetch('/process-drive-url', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: url })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        resultDiv.innerHTML = `<div class="success">${data.message}</div>`;
                    } else {
                        resultDiv.innerHTML = `<div class="error">Error: ${data.detail}</div>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }

            async function sendQuery() {
                const query = document.getElementById('chatQuery').value;
                const resultDiv = document.getElementById('chatResult');
                
                if (!query) {
                    resultDiv.innerHTML = '<div class="error">Please enter a question</div>';
                    return;
                }

                try {
                    resultDiv.innerHTML = '<div>Thinking...</div>';
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: query })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        let sourcesHtml = '';
                        if (data.sources && data.sources.length > 0) {
                            sourcesHtml = '<div class="sources"><h4>Sources:</h4>';
                            data.sources.forEach((source, index) => {
                                sourcesHtml += `<p><strong>${index + 1}.</strong> ${source.filename} (${source.doc_id}:${source.chunk_id})</p>`;
                            });
                            sourcesHtml += '</div>';
                        }
                        
                        resultDiv.innerHTML = `
                            <div class="response">
                                <h4>Answer:</h4>
                                <p>${data.answer}</p>
                                ${sourcesHtml}
                                <small>Context chunks used: ${data.context_count} | Model: ${data.model_used}</small>
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `<div class="error">Error: ${data.detail}</div>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }

            async function checkHealth() {
                const resultDiv = document.getElementById('healthResult');
                
                try {
                    const response = await fetch('/health');
                    const data = await response.json();
                    
                    let statusColor = data.redis_healthy ? 'success' : 'error';
                    resultDiv.innerHTML = `
                        <div class="${statusColor}">
                            <h4>System Status: ${data.status}</h4>
                            <p>Redis: ${data.redis_healthy ? '✅ Healthy' : '❌ Unhealthy'}</p>
                            <p>Services: ${JSON.stringify(data.services, null, 2)}</p>
                        </div>
                    `;
                } catch (error) {
                    resultDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }

            async function setupWebhook() {
                const folderId = document.getElementById('folderId').value;
                const resultDiv = document.getElementById('webhookResult');
                
                try {
                    resultDiv.innerHTML = '<div>Setting up webhook...</div>';
                    
                    const requestBody = folderId ? { folder_id: folderId } : {};
                    
                    const response = await fetch('/webhooks/setup', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(requestBody)
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        const scopeText = folderId ? `folder ${folderId}` : 'all Google Drive files';
                        resultDiv.innerHTML = `
                            <div class="success">
                                <h4>Webhook Setup Complete! 🎉</h4>
                                <p><strong>Monitoring:</strong> ${scopeText}</p>
                                <p><strong>Webhook URL:</strong> ${data.webhook_url}</p>
                                <p><strong>Watch ID:</strong> ${data.watch_id}</p>
                                <p><strong>Security:</strong> ${data.security_enabled ? '✅ Enabled' : '❌ Disabled'}</p>
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `<div class="error">Error: ${data.detail}</div>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    redis_healthy = redis_store.health_check()
    
    services = {
        "redis": "healthy" if redis_healthy else "unhealthy",
        "embedding_service": "healthy",
        "chat_service": "healthy"
    }
    
    return HealthResponse(
        status="healthy" if redis_healthy else "degraded",
        redis_healthy=redis_healthy,
        services=services
    )


@app.post("/upload-documents", response_model=List[DocumentUploadResponse])
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Upload and process multiple documents."""
    results = []
    
    for file in files:
        try:
            # Check file type
            if not document_processor.is_supported_file(file.filename):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file type: {file.filename}"
                )
            
            # Save uploaded file
            file_path = os.path.join(settings.upload_dir, file.filename)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Process document in background
            background_tasks.add_task(process_document_task, file_path, "")
            
            results.append(DocumentUploadResponse(
                doc_id="processing",
                filename=file.filename,
                chunks_count=0,
                message=f"File {file.filename} uploaded and queued for processing"
            ))
            
        except Exception as e:
            logger.error(f"Error uploading file {file.filename}: {str(e)}")
            results.append(DocumentUploadResponse(
                doc_id="error",
                filename=file.filename,
                chunks_count=0,
                message=f"Error processing {file.filename}: {str(e)}"
            ))
    
    return results


async def process_document_task(file_path: str, source_url: str):
    """Background task to process a document."""
    try:
        # Process document
        doc_id, chunks, metadata = document_processor.process_file(file_path, source_url)
        
        # Generate embeddings and store chunks
        texts = [chunk["text"] for chunk in chunks]
        embeddings = embedding_service.generate_embeddings_batch(texts)
        
        # Store chunks in Redis
        for chunk, embedding in zip(chunks, embeddings):
            redis_store.store_chunk(
                doc_id=chunk["doc_id"],
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                embedding=embedding,
                source_url=chunk["source_url"],
                filename=chunk["filename"],
                last_modified=chunk["last_modified"]
            )
        
        logger.info(f"Successfully processed and stored document {doc_id}")
        
        # Clean up temporary file
        if os.path.exists(file_path) and file_path.startswith(settings.upload_dir):
            os.remove(file_path)
            
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")


@app.post("/process-drive-url")
async def process_drive_url(
    request: GoogleDriveRequest,
    background_tasks: BackgroundTasks
):
    """Process a Google Drive URL."""
    try:
        # Extract file ID from URL
        file_id = google_drive_service.extract_file_id_from_url(request.url)
        if not file_id:
            raise HTTPException(status_code=400, detail="Invalid Google Drive URL")
        
        # Check if authenticated
        if not google_drive_service.is_authenticated():
            # Try to load existing credentials
            if not google_drive_service.load_credentials():
                raise HTTPException(
                    status_code=401, 
                    detail="Google Drive authentication required. Please authenticate first."
                )
        
        # Process in background
        background_tasks.add_task(process_google_drive_task, request.url, file_id)
        
        return {"message": f"Google Drive content queued for processing: {request.url}"}
        
    except Exception as e:
        logger.error(f"Error processing Google Drive URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_google_drive_task(url: str, file_id: str):
    """Background task for processing Google Drive content."""
    try:
        # Check if it's a single file or folder
        metadata = google_drive_service.get_file_metadata(file_id)
        if not metadata:
            logger.error(f"Could not get metadata for file {file_id}")
            return
        
        mime_type = metadata.get('mimeType', '')
        
        if 'folder' in mime_type:
            # Process folder
            files = google_drive_service.list_folder_files(url)
            for file_info in files:
                await process_single_drive_file(file_info['id'], file_info['webViewLink'])
        else:
            # Process single file
            await process_single_drive_file(file_id, url)
            
    except Exception as e:
        logger.error(f"Error in Google Drive background processing: {str(e)}")


async def process_single_drive_file(file_id: str, url: str):
    """Process a single Google Drive file."""
    try:
        # Download content
        content = google_drive_service.download_file_content(file_id)
        if not content:
            logger.error(f"Could not download content for file {file_id}")
            return
        
        # If content is a file path (for binary files), process it
        if content.startswith("temp_"):
            doc_id, chunks, metadata = document_processor.process_file(content, url)
            # Clean up temp file
            if os.path.exists(content):
                os.remove(content)
        else:
            # Process text content directly
            doc_id = document_processor.generate_doc_id(content, url)
            chunks = document_processor.chunk_text(content, doc_id)
            
            # Add metadata to chunks
            for chunk in chunks:
                chunk.update({
                    "source_url": url,
                    "filename": f"gdrive_doc_{doc_id}",
                    "last_modified": time.time()
                })
        
        # Generate embeddings and store
        texts = [chunk["text"] for chunk in chunks]
        embeddings = embedding_service.generate_embeddings_batch(texts)
        
        for chunk, embedding in zip(chunks, embeddings):
            redis_store.store_chunk(
                doc_id=chunk["doc_id"],
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                embedding=embedding,
                source_url=chunk["source_url"],
                filename=chunk["filename"],
                last_modified=chunk["last_modified"]
            )
        
        logger.info(f"Successfully processed Google Drive file: {file_id}")
        
    except Exception as e:
        logger.error(f"Error processing Google Drive file {file_id}: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat with the knowledge base."""
    try:
        # Use contextual chat if history provided
        if request.chat_history:
            response = chat_service.contextual_chat(
                query=request.query,
                chat_history=request.chat_history,
                top_k=request.top_k
            )
        else:
            response = chat_service.chat(
                query=request.query,
                top_k=request.top_k,
                use_hybrid_search=request.use_hybrid_search
            )
        
        return ChatResponse(**response)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/google/login")
async def google_auth_login():
    """Initiate Google Drive OAuth flow using configured credentials."""
    try:
        # Use credentials from settings
        auth_url = google_drive_service.setup_credentials(
            settings.google_client_id, 
            settings.google_client_secret
        )
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error initiating Google auth: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Authentication setup failed: {str(e)}")


@app.get("/auth/google")
async def google_auth_setup(client_id: str, client_secret: str):
    """Setup Google Drive authentication."""
    try:
        auth_url = google_drive_service.setup_credentials(client_id, client_secret)
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/google/callback")
async def google_auth_callback(code: str):
    """Handle Google Drive authentication callback."""
    try:
        success = google_drive_service.authenticate_with_code(code)
        if success:
            return {"message": "Successfully authenticated with Google Drive"}
        else:
            raise HTTPException(status_code=400, detail="Authentication failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/drive")
async def drive_webhook(request: Request):
    """Handle Google Drive webhook notifications"""
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Get signature from headers
        signature = request.headers.get('X-Goog-Channel-Token', '')
        
        # Verify webhook signature
        if not webhook_service.verify_webhook_signature(body, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Parse notification data
        notification_data = await request.json()
        
        # Process the notification
        result = await webhook_service.handle_drive_notification(notification_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing Drive webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/setup")
async def setup_webhook(folder_id: Optional[str] = None):
    """Setup Google Drive webhook for automatic change detection"""
    try:
        result = webhook_service.setup_drive_webhook(folder_id)
        return result
        
    except Exception as e:
        logger.error(f"Error setting up webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/google-drive/folders")
async def list_google_drive_folders():
    """List Google Drive folders to help find folder IDs"""
    try:
        if not google_drive_service.is_authenticated():
            raise HTTPException(
                status_code=401, 
                detail="Google Drive authentication required. Please authenticate first at /auth/google/login"
            )
        
        # Get folders from Google Drive
        folders = google_drive_service.list_folders()
        
        return {
            "folders": folders,
            "total_count": len(folders),
            "note": "Use the 'id' field from any folder to set up webhooks for that specific folder"
        }
        
    except Exception as e:
        logger.error(f"Error listing Google Drive folders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    """List all processed documents with their metadata"""
    try:
        # Get all document mappings
        documents = []
        
        # Scan for all drive mappings
        for key in redis_store.redis_client.scan_iter(match="drive_mapping:*"):
            doc_data = redis_store.redis_client.hgetall(key)
            if doc_data:
                # Get chunk count
                chunks = redis_store.get_document_chunks(doc_data.get('doc_id', ''))
                doc_data['chunk_count'] = len(chunks)
                documents.append(doc_data)
        
        return {
            "documents": documents,
            "total_count": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and all its chunks"""
    try:
        # Get document chunks
        chunks = redis_store.get_document_chunks(doc_id)
        
        if not chunks:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Remove all chunks
        for chunk in chunks:
            redis_store.delete_chunk(chunk['chunk_id'])
        
        # Remove document metadata
        redis_store.delete_document(doc_id)
        
        return {
            "message": f"Successfully deleted document {doc_id}",
            "chunks_removed": len(chunks)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/monitoring/start")
async def start_file_monitoring(directory: str):
    """Start monitoring a directory for file changes"""
    try:
        success = file_monitor_service.start_monitoring(directory)
        if success:
            return {"message": f"Started monitoring directory: {directory}"}
        else:
            raise HTTPException(status_code=400, detail="Failed to start monitoring")
    except Exception as e:
        logger.error(f"Error starting file monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/monitoring/stop")
async def stop_file_monitoring(directory: str):
    """Stop monitoring a directory"""
    try:
        success = file_monitor_service.stop_monitoring(directory)
        if success:
            return {"message": f"Stopped monitoring directory: {directory}"}
        else:
            raise HTTPException(status_code=400, detail="Directory not being monitored")
    except Exception as e:
        logger.error(f"Error stopping file monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/monitoring/status")
async def get_monitoring_status():
    """Get file monitoring status"""
    try:
        status = file_monitor_service.get_monitoring_status()
        return status
    except Exception as e:
        logger.error(f"Error getting monitoring status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Load Google Drive credentials if available
    google_drive_service.load_credentials()
    
    # Run the application
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    ) 