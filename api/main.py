import os
import sys
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import tempfile
import shutil

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import our modules with fallbacks
try:
    from config import settings
    from redis_client import redis_store
    from embedding_service import embedding_service
    from document_processor import document_processor
    from chat_service import chat_service
    CONFIG_AVAILABLE = True
except ImportError as e:
    print(f"Import error: {e}")
    CONFIG_AVAILABLE = False

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

# Pydantic models
class ChatRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    query: str

class HealthResponse(BaseModel):
    status: str
    message: str

@app.get("/", response_class=HTMLResponse)
async def root():
    """Simple web interface."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redis RAG Chatbot - Vercel</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
            input, textarea { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            .response { background: #e9ecef; padding: 15px; border-radius: 4px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Redis RAG Chatbot</h1>
            <p>Deployed on Vercel! 🚀</p>
            
            <div class="section">
                <h2>💬 Chat</h2>
                <textarea id="query" rows="3" placeholder="Ask a question..."></textarea>
                <button onclick="sendQuery()">Send Query</button>
                <div id="result"></div>
            </div>
            
            <div class="section">
                <h2>📄 Upload Document</h2>
                <input type="file" id="file" accept=".pdf,.docx,.txt">
                <button onclick="uploadFile()">Upload</button>
                <div id="uploadResult"></div>
            </div>
        </div>
        
        <script>
            async function sendQuery() {
                const query = document.getElementById('query').value;
                const result = document.getElementById('result');
                
                if (!query) return;
                
                try {
                    result.innerHTML = '<div>Processing...</div>';
                    const response = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: query })
                    });
                    
                    const data = await response.json();
                    result.innerHTML = `<div class="response"><strong>Answer:</strong> ${data.answer}</div>`;
                } catch (error) {
                    result.innerHTML = `<div style="color: red;">Error: ${error.message}</div>`;
                }
            }
            
            async function uploadFile() {
                const fileInput = document.getElementById('file');
                const result = document.getElementById('uploadResult');
                
                if (!fileInput.files[0]) return;
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                
                try {
                    result.innerHTML = '<div>Uploading...</div>';
                    const response = await fetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    result.innerHTML = `<div class="response">Success: ${data.message}</div>`;
                } catch (error) {
                    result.innerHTML = `<div style="color: red;">Error: ${error.message}</div>`;
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    try:
        if CONFIG_AVAILABLE:
            # Try to ping Redis
            redis_healthy = redis_store.redis_client.ping() if redis_store else False
            return HealthResponse(
                status="healthy" if redis_healthy else "degraded",
                message="All systems operational" if redis_healthy else "Redis connection issues"
            )
        else:
            return HealthResponse(status="degraded", message="Configuration not loaded")
    except Exception as e:
        return HealthResponse(status="unhealthy", message=f"Error: {str(e)}")

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Chat endpoint."""
    try:
        if not CONFIG_AVAILABLE:
            raise HTTPException(status_code=503, detail="Service configuration not available")
        
        # Use chat service if available
        response = await chat_service.generate_response(
            query=request.query,
            top_k=request.top_k or 5
        )
        
        return ChatResponse(
            answer=response["answer"],
            sources=response.get("sources", []),
            query=request.query
        )
    except Exception as e:
        # Fallback response
        return ChatResponse(
            answer=f"I'm currently unable to process your query. Error: {str(e)}",
            sources=[],
            query=request.query
        )

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process document."""
    try:
        if not CONFIG_AVAILABLE:
            raise HTTPException(status_code=503, detail="Service configuration not available")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name
        
        try:
            # Process document
            doc_id, chunks, metadata = document_processor.process_file(tmp_path)
            
            # Generate embeddings and store
            texts = [chunk["text"] for chunk in chunks]
            embeddings = embedding_service.generate_embeddings(texts)
            
            # Store in Redis
            for chunk, embedding in zip(chunks, embeddings):
                redis_store.store_chunk(chunk, embedding)
            
            return {
                "message": f"Successfully processed {file.filename} with {len(chunks)} chunks",
                "doc_id": doc_id,
                "chunks_count": len(chunks)
            }
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

# Export for Vercel
handler = app 