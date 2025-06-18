# Ultra-lightweight build using Alpine Linux
FROM python:3.11-alpine as builder

# Install build dependencies in minimal batches
RUN apk add --no-cache gcc musl-dev libffi-dev

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements and install in smaller batches to avoid memory issues
COPY requirements.txt .

# Install core dependencies first (most stable)
RUN pip install --no-cache-dir fastapi==0.104.1 uvicorn[standard]==0.24.0

# Install Redis and basic utilities
RUN pip install --no-cache-dir redis==5.0.1 python-dotenv==1.0.0 requests==2.31.0

# Install OpenAI and document processing
RUN pip install --no-cache-dir openai==1.3.7 pypdf==3.17.1 python-docx==1.1.0

# Install remaining dependencies
RUN pip install --no-cache-dir python-multipart==0.0.6 httpx==0.25.2 aiofiles==23.2.0

# Install pydantic and related
RUN pip install --no-cache-dir "pydantic>=2.3.0,<3.0.0" pydantic-settings==2.1.0 typing-extensions==4.8.0

# Install Google Drive dependencies
RUN pip install --no-cache-dir google-api-python-client==2.108.0 google-auth-httplib2==0.1.1 google-auth-oauthlib==1.1.0

# Install remaining packages
RUN pip install --no-cache-dir watchdog==4.0.0 "numpy>=1.24.0,<2.0.0" "setuptools>=65.0.0"

# Try to install unstructured last (most likely to cause issues)
RUN pip install --no-cache-dir unstructured==0.11.8 || echo "Unstructured installation failed, will use fallback"

# Final runtime stage - Alpine Linux
FROM python:3.11-alpine

# Install only essential runtime dependencies
RUN apk add --no-cache ca-certificates

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application files
COPY *.py ./
RUN mkdir -p uploads

# Non-root user for security
RUN adduser -D -s /bin/sh app && chown -R app:app /app
USER app

# Expose port
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:$PORT/health')" || exit 1

# Start command
CMD uvicorn main:app --host 0.0.0.0 --port $PORT 