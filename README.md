# 🤖 Redis RAG Chatbot

A comprehensive Retrieval-Augmented Generation (RAG) chatbot system powered by Redis as the vector database. This system allows you to upload documents, integrate with Google Drive, and chat with your knowledge base using advanced hybrid search capabilities.

## 🚀 Features

### Document Processing
- ✅ **Multi-format Support**: PDF, DOCX, MD, TXT, Google Docs
- ✅ **Intelligent Chunking**: Using unstructured.io for optimal text extraction
- ✅ **Redis Vector Storage**: Fast vector similarity search with HNSW indexing
- ✅ **Source Attribution**: Track and reference original documents

### Google Drive Integration
- ✅ **Direct URL Processing**: Support for Google Docs, Sheets, Slides
- ✅ **Folder Processing**: Batch process entire Google Drive folders
- ✅ **Change Detection**: Monitor and re-index updated documents
- ✅ **Authentication Flow**: OAuth2 integration for secure access

### Advanced Search & Chat
- ✅ **Hybrid Search**: Combines vector similarity + keyword matching
- ✅ **Contextual Chat**: Maintains conversation history
- ✅ **Source Citations**: Every answer includes document references
- ✅ **Configurable Results**: Adjustable top-K results and search weights

### Web Interface
- ✅ **Responsive UI**: Built-in web interface for easy interaction
- ✅ **File Upload**: Drag-and-drop document upload
- ✅ **Real-time Chat**: Interactive chatbot interface
- ✅ **Health Monitoring**: System status and diagnostics

## 🛠️ Installation & Setup

### Prerequisites

1. **Redis with RediSearch module** (for vector search)
2. **Python 3.8+**
3. **OpenAI API Key**
4. **Google Drive API credentials** (optional, for Google Drive integration)

### Step 1: Install Redis with RediSearch

```bash
# Option 1: Using Docker (Recommended)
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server:latest

# Option 2: Using Redis Stack locally
# Download from: https://redis.io/download
```

### Step 2: Clone and Install Dependencies

```bash
git clone <your-repo-url>
cd redis-rag-chatbot

# Install Python dependencies
pip install -r requirements.txt
```

### Step 3: Environment Configuration

Create a `.env` file in the project root:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# OpenAI Configuration (Required)
OPENAI_API_KEY=your_openai_api_key_here
EMBEDDING_MODEL=text-embedding-ada-002
CHAT_MODEL=gpt-3.5-turbo

# Google Drive API Configuration (Optional)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Application Configuration
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=True
MAX_CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K_RESULTS=5

# File Upload Configuration
MAX_FILE_SIZE=50MB
UPLOAD_DIR=./uploads

# Webhook Configuration
WEBHOOK_SECRET=your_webhook_secret_here
```

### Step 4: Google Drive Setup (Optional)

If you want to use Google Drive integration:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Drive API
4. Create OAuth 2.0 credentials (Web application)
5. Add `http://localhost:8000/auth/google/callback` to authorized redirect URIs
6. Copy Client ID and Client Secret to your `.env` file

## 🚀 Running the Application

### Start the Server

```bash
# Development mode
python main.py

# Or using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Access the Web Interface

Open your browser and navigate to: `http://localhost:8000`

## 📖 Usage Guide

### 1. Document Upload

#### Via Web Interface:
1. Visit `http://localhost:8000`
2. Use the "Upload Documents" section
3. Select multiple PDF, DOCX, MD, or TXT files
4. Click "Upload Files"

#### Via API:
```bash
curl -X POST "http://localhost:8000/upload-documents" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@document1.pdf" \
  -F "files=@document2.docx"
```

### 2. Google Drive Integration

#### Setup Authentication:
```bash
# Get authentication URL
curl "http://localhost:8000/auth/google?client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET"

# Follow the returned auth_url to authorize
# The callback will complete the authentication
```

#### Process Google Drive Content:
```bash
# Single document
curl -X POST "http://localhost:8000/process-drive-url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.google.com/document/d/YOUR_DOC_ID/edit"}'

# Entire folder
curl -X POST "http://localhost:8000/process-drive-url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://drive.google.com/drive/folders/YOUR_FOLDER_ID"}'
```

### 3. Chat with Documents

#### Via Web Interface:
1. Use the "Chat with Your Documents" section
2. Type your question
3. Click "Send Query"
4. View answer with source citations

#### Via API:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main topics discussed in the documents?",
    "top_k": 5,
    "use_hybrid_search": true
  }'
```

#### With Chat History:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Can you elaborate on that?",
    "chat_history": [
      {"role": "user", "content": "What is machine learning?"},
      {"role": "assistant", "content": "Machine learning is..."}
    ]
  }'
```

## 🔧 API Endpoints

### Document Management
- `POST /upload-documents` - Upload multiple documents
- `POST /process-drive-url` - Process Google Drive URL
- `GET /documents` - List all documents
- `DELETE /documents/{doc_id}` - Delete a document

### Chat & Search
- `POST /chat` - Chat with the knowledge base
- Advanced parameters: `top_k`, `use_hybrid_search`, `chat_history`

### Authentication
- `GET /auth/google` - Setup Google Drive authentication
- `GET /auth/google/callback` - OAuth callback handler

### System
- `GET /health` - System health check
- `GET /` - Web interface

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Interface │    │   FastAPI App   │    │   Background    │
│                 │────│                 │────│   Tasks         │
│   - File Upload │    │  - API Routes   │    │  - Doc Process  │
│   - Chat UI     │    │  - Auth Flow    │    │  - Embedding    │
│   - Drive Input │    │  - Validation   │    │  - Indexing     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ Document        │ │ Embedding       │ │ Google Drive    │
    │ Processor       │ │ Service         │ │ Service         │
    │                 │ │                 │ │                 │
    │ - unstructured  │ │ - OpenAI API    │ │ - OAuth Flow    │
    │ - Text Extract  │ │ - Batch Process │ │ - File Download │
    │ - Chunking      │ │ - ada-002       │ │ - Change Detect │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
                │               │               │
                └───────────────┼───────────────┘
                                │
                    ┌─────────────────┐
                    │ Redis Vector DB │
                    │                 │
                    │ - HNSW Index    │
                    │ - Hybrid Search │
                    │ - Chunk Storage │
                    │ - Metadata      │
                    └─────────────────┘
                                │
                    ┌─────────────────┐
                    │ Chat Service    │
                    │                 │
                    │ - Context Retr. │
                    │ - LLM Generation│
                    │ - Source Citing │
                    │ - Chat History  │
                    └─────────────────┘
```

## 🔍 Configuration Options

### Search Parameters
- `MAX_CHUNK_SIZE`: Maximum characters per chunk (default: 1000)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 200)
- `TOP_K_RESULTS`: Number of results to retrieve (default: 5)

### Vector Search
- **Distance Metric**: Cosine similarity
- **Index Type**: HNSW (Hierarchical Navigable Small World)
- **Vector Dimensions**: 1536 (OpenAI ada-002)

### Hybrid Search Weights
- **Vector Weight**: 0.7 (semantic similarity)
- **Text Weight**: 0.3 (keyword matching)

## 🐛 Troubleshooting

### Common Issues

1. **Redis Connection Error**
   ```bash
   # Check if Redis is running
   redis-cli ping
   # Should return "PONG"
   ```

2. **RediSearch Module Missing**
   ```bash
   # Verify RediSearch is loaded
   redis-cli MODULE LIST
   # Should show "search" module
   ```

3. **OpenAI API Errors**
   - Check your API key is valid
   - Verify you have sufficient credits
   - Check rate limits

4. **Google Drive Authentication**
   - Verify redirect URI matches exactly
   - Check OAuth consent screen setup
   - Ensure Drive API is enabled

### Logs and Debugging

```bash
# View application logs
tail -f app.log

# Enable debug logging
export DEBUG=True

# Check Redis index status
redis-cli FT.INFO doc_chunks_idx
```

## 📈 Performance Optimization

### Redis Tuning
```bash
# Increase memory limits
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Optimize for vector search
redis-cli CONFIG SET save ""  # Disable snapshotting for speed
```

### Embedding Optimization
- Use batch processing for multiple documents
- Consider caching embeddings for repeated content
- Monitor OpenAI API rate limits

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Redis**: For powerful vector search capabilities
- **OpenAI**: For embeddings and chat completions
- **unstructured.io**: For document processing
- **FastAPI**: For the robust web framework
- **Google Drive API**: For document integration

---

## 🆘 Support

If you encounter any issues or have questions:

1. Check the troubleshooting section above
2. Review the logs for error details
3. Open an issue on GitHub with:
   - Error messages
   - Steps to reproduce
   - Environment details

Happy chatting with your documents! 🚀 