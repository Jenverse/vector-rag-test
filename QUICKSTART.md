# ⚡ Quick Start Guide

Get your Redis RAG Chatbot running in 5 minutes!

## 🚀 Prerequisites

1. **Python 3.8+** installed
2. **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))
3. **Redis with RediSearch** (see options below)

## 📦 Option 1: Quick Setup with Docker (Recommended)

```bash
# 1. Start Redis Stack (includes RediSearch)
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server:latest

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set up environment
cp env_template.txt .env
# Edit .env and add your OPENAI_API_KEY

# 4. Run the startup script
python start.py
```

## 🔧 Option 2: Manual Setup

### Step 1: Install Redis Stack

**On macOS:**
```bash
brew tap redis-stack/redis-stack
brew install redis-stack
redis-stack-server
```

**On Ubuntu/Debian:**
```bash
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
sudo apt-get update
sudo apt-get install redis-stack-server
redis-stack-server
```

**Using Docker:**
```bash
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server:latest
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
# Copy template
cp env_template.txt .env

# Edit .env file and set:
OPENAI_API_KEY=your_actual_api_key_here
```

### Step 4: Start the Application

```bash
# Option A: Use the startup script (recommended)
python start.py

# Option B: Direct start
python main.py

# Option C: With uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 🎯 First Test

1. **Open your browser**: http://localhost:8000
2. **Upload a document**: Use the file upload section
3. **Wait for processing**: Check the logs for processing completion
4. **Ask a question**: Use the chat interface

## 📝 Example Usage

### Upload Documents
```bash
curl -X POST "http://localhost:8000/upload-documents" \
  -F "files=@document.pdf"
```

### Chat with Documents
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?"}'
```

## 🔍 Health Check

```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "redis_healthy": true,
  "services": {
    "redis": "healthy",
    "embedding_service": "healthy",
    "chat_service": "healthy"
  }
}
```

## 🐛 Common Issues

### "Redis connection failed"
- Make sure Redis is running: `redis-cli ping`
- Check if RediSearch module is loaded: `redis-cli MODULE LIST`

### "OpenAI API error"
- Verify your API key is correct
- Check you have credits in your OpenAI account

### "Module not found" errors
- Run: `pip install -r requirements.txt`

## 🚀 Next Steps

1. **Add Google Drive integration**: Set up Google Cloud credentials
2. **Upload more documents**: Try different file formats (PDF, DOCX, MD)
3. **Experiment with settings**: Adjust chunk size, top-K results, etc.
4. **Scale up**: Use production Redis setup for larger datasets

## 💡 Tips

- **Chunk Size**: Smaller chunks (500-1000 chars) work better for specific questions
- **Overlap**: 200-300 character overlap helps maintain context
- **Model Choice**: Use gpt-3.5-turbo for speed, gpt-4 for quality
- **Batch Processing**: Upload multiple documents at once for efficiency

## 🆘 Need Help?

- Check the [full documentation](README.md)
- Review the troubleshooting section
- Check application logs for detailed error messages

Happy chatting! 🤖 