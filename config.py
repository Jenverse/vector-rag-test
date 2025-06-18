import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator


class Settings(BaseSettings):
    # Redis Configuration
    redis_url: Optional[str] = None  # Full Redis URL (takes precedence)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    
    # Embedding Configuration
    embedding_provider: str = "openai"  # "openai" or "local"
    openai_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-ada-002"  # For OpenAI
    local_embedding_model: str = "all-MiniLM-L6-v2"  # Lightweight local model
    chat_model: str = "gpt-3.5-turbo"
    
    # Google Drive API Configuration
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    
    # Application Configuration
    app_host: str = "0.0.0.0"
    app_port: int = int(os.getenv("PORT", "8000"))  # Railway sets PORT automatically
    app_base_url: str = os.getenv("RAILWAY_STATIC_URL", "http://localhost:8000")  # Railway public URL
    debug: bool = os.getenv("RAILWAY_ENVIRONMENT") != "production"
    max_chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 5
    
    # File Upload Configuration
    max_file_size: str = "50MB"
    upload_dir: str = "./uploads"
    
    # Webhook Configuration
    webhook_secret: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_openai_key(self):
        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ValueError("openai_api_key is required when embedding_provider is 'openai'")
        return self
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True) 