import openai
from typing import List, Union
import logging
from config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = openai.OpenAI(api_key=settings.openai_api_key)


class EmbeddingService:
    def __init__(self):
        """Initialize the embedding service."""
        self.model = settings.embedding_model
        self.max_tokens = 8191  # Max tokens for text-embedding-ada-002
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            # Truncate text if too long
            if len(text) > self.max_tokens:
                text = text[:self.max_tokens]
            
            response = client.embeddings.create(
                input=text,
                model=self.model
            )
            
            embedding = response.data[0].embedding
            logger.info(f"Generated embedding for text of length {len(text)}")
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise e
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch."""
        try:
            # Process texts in batches to avoid API limits
            batch_size = 100
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # Truncate texts if too long
                truncated_texts = []
                for text in batch_texts:
                    if len(text) > self.max_tokens:
                        text = text[:self.max_tokens]
                    truncated_texts.append(text)
                
                response = client.embeddings.create(
                    input=truncated_texts,
                    model=self.model
                )
                
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)
            
            logger.info(f"Generated embeddings for {len(texts)} texts")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            raise e
    
    def get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a search query."""
        return self.generate_embedding(query)


# Global embedding service instance
embedding_service = EmbeddingService() 