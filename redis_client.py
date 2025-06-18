import json
import numpy as np
from typing import List, Dict, Any, Optional
import redis
from redis.commands.search.field import VectorField, TextField, NumericField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from config import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RedisVectorStore:
    def __init__(self):
        """Initialize Redis connection and vector search index."""
        # Use Redis URL if provided, otherwise use individual settings
        if settings.redis_url:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
        else:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True
            )
        
        # Index name for document chunks
        self.index_name = "doc_chunks_idx"
        self.chunk_prefix = "doc_chunk:"
        
        # Vector dimensions (OpenAI text-embedding-ada-002 = 1536)
        self.vector_dim = 1536
        
        # Initialize the search index
        self._create_index()
    
    def _create_index(self):
        """Create Redis search index for document chunks."""
        try:
            # Check if index already exists
            self.redis_client.ft(self.index_name).info()
            logger.info(f"Index {self.index_name} already exists")
        except redis.ResponseError:
            # Create new index
            logger.info(f"Creating new index: {self.index_name}")
            
            schema = [
                TextField("doc_id"),
                TextField("chunk_id"),
                TextField("text"),
                TextField("source_url"),
                TextField("filename"),
                NumericField("last_modified"),
                VectorField(
                    "embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.vector_dim,
                        "DISTANCE_METRIC": "COSINE"
                    }
                )
            ]
            
            definition = IndexDefinition(
                prefix=[self.chunk_prefix],
                index_type=IndexType.HASH
            )
            
            self.redis_client.ft(self.index_name).create_index(
                schema, definition=definition
            )
            logger.info(f"Successfully created index: {self.index_name}")
    
    def store_chunk(
        self,
        doc_id: str,
        chunk_id: str,
        text: str,
        embedding: List[float],
        source_url: str = "",
        filename: str = "",
        last_modified: float = 0
    ) -> bool:
        """Store a document chunk with its embedding in Redis."""
        try:
            key = f"{self.chunk_prefix}{doc_id}:{chunk_id}"
            
            # Convert embedding to bytes
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
            
            chunk_data = {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "text": text,
                "source_url": source_url,
                "filename": filename,
                "last_modified": last_modified,
                "embedding": embedding_bytes
            }
            
            # Store in Redis
            self.redis_client.hset(key, mapping=chunk_data)
            logger.info(f"Stored chunk: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing chunk {doc_id}:{chunk_id}: {str(e)}")
            return False
    
    def vector_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        try:
            # Convert query embedding to bytes
            query_vector = np.array(query_embedding, dtype=np.float32).tobytes()
            
            # Build query
            base_query = f"*=>[KNN {top_k} @embedding $query_vector AS vector_score]"
            
            # Add filters if provided
            if filter_dict:
                filter_clauses = []
                for field, value in filter_dict.items():
                    filter_clauses.append(f"@{field}:{value}")
                base_query = f"({' '.join(filter_clauses)}) => [KNN {top_k} @embedding $query_vector AS vector_score]"
            
            query = Query(base_query).return_fields(
                "doc_id", "chunk_id", "text", "source_url", "filename", 
                "last_modified", "vector_score"
            ).sort_by("vector_score").dialect(2)
            
            # Execute search
            results = self.redis_client.ft(self.index_name).search(
                query, {"query_vector": query_vector}
            )
            
            # Format results
            formatted_results = []
            for doc in results.docs:
                result = {
                    "doc_id": doc.doc_id,
                    "chunk_id": doc.chunk_id,
                    "text": doc.text,
                    "source_url": doc.source_url,
                    "filename": doc.filename,
                    "last_modified": float(doc.last_modified),
                    "score": float(doc.vector_score)
                }
                formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in vector search: {str(e)}")
            return []
    
    def hybrid_search(
        self,
        query_embedding: List[float],
        text_query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        text_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector similarity and text search."""
        try:
            # Vector search
            vector_results = self.vector_search(query_embedding, top_k * 2)
            
            # Text search
            text_query_escaped = text_query.replace("-", "\\-").replace(".", "\\.")
            text_search_query = Query(f"@text:{text_query_escaped}").return_fields(
                "doc_id", "chunk_id", "text", "source_url", "filename", "last_modified"
            ).limit(0, top_k * 2)
            
            text_results = self.redis_client.ft(self.index_name).search(text_search_query)
            
            # Convert text results to same format
            text_results_formatted = []
            for doc in text_results.docs:
                result = {
                    "doc_id": doc.doc_id,
                    "chunk_id": doc.chunk_id,
                    "text": doc.text,
                    "source_url": doc.source_url,
                    "filename": doc.filename,
                    "last_modified": float(doc.last_modified),
                    "text_match": True
                }
                text_results_formatted.append(result)
            
            # Combine and score results
            combined_results = {}
            
            # Add vector results with vector weight
            for result in vector_results:
                key = f"{result['doc_id']}:{result['chunk_id']}"
                combined_results[key] = result.copy()
                combined_results[key]["combined_score"] = (1 - result["score"]) * vector_weight
            
            # Add text results with text weight
            for result in text_results_formatted:
                key = f"{result['doc_id']}:{result['chunk_id']}"
                if key in combined_results:
                    # Boost existing results that match both
                    combined_results[key]["combined_score"] += text_weight
                    combined_results[key]["text_match"] = True
                else:
                    # Add new text-only matches
                    result["combined_score"] = text_weight
                    combined_results[key] = result
            
            # Sort by combined score and return top_k
            sorted_results = sorted(
                combined_results.values(),
                key=lambda x: x["combined_score"],
                reverse=True
            )
            
            return sorted_results[:top_k]
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            return self.vector_search(query_embedding, top_k)
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a document"""
        try:
            # Search for chunks belonging to this document
            query = f"@doc_id:{doc_id}"
            
            results = self.redis_client.ft(self.index_name).search(
                query, 
                query_params={}
            )
            
            chunks = []
            for doc in results.docs:
                chunk_data = {
                    "chunk_id": doc.id.replace(self.chunk_prefix, ""),
                    "doc_id": doc.doc_id,
                    "content": doc.content,
                    "metadata": json.loads(doc.metadata) if hasattr(doc, 'metadata') else {}
                }
                chunks.append(chunk_data)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error retrieving document chunks: {str(e)}")
            return []
    
    def delete_document_chunks(self, doc_id: str) -> bool:
        """Delete all chunks for a specific document."""
        try:
            chunks = self.get_document_chunks(doc_id)
            
            for chunk in chunks:
                key = f"{self.chunk_prefix}{chunk['doc_id']}:{chunk['chunk_id']}"
                self.redis_client.delete(key)
            
            logger.info(f"Deleted {len(chunks)} chunks for document {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document chunks for {doc_id}: {str(e)}")
            return False
    
    def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def store_drive_document_mapping(self, drive_id: str, doc_id: str, metadata: Dict[str, Any]):
        """Store mapping between Google Drive ID and document ID"""
        mapping_key = f"drive_mapping:{drive_id}"
        mapping_data = {
            "doc_id": doc_id,
            "drive_id": drive_id,
            "created_at": datetime.now().isoformat(),
            "modified_time": metadata.get('modifiedTime'),
            "name": metadata.get('name'),
            "mime_type": metadata.get('mimeType'),
            **metadata
        }
        
        self.redis_client.hset(mapping_key, mapping=mapping_data)
        logger.info(f"Stored Drive mapping: {drive_id} -> {doc_id}")
    
    def get_document_by_drive_id(self, drive_id: str) -> Optional[Dict[str, Any]]:
        """Get document info by Google Drive ID"""
        mapping_key = f"drive_mapping:{drive_id}"
        mapping_data = self.redis_client.hgetall(mapping_key)
        
        if mapping_data:
            return mapping_data
        return None
    
    def delete_document(self, doc_id: str):
        """Delete document metadata"""
        doc_key = f"document:{doc_id}"
        self.redis_client.delete(doc_key)
        logger.info(f"Deleted document metadata: {doc_id}")
    
    def delete_chunk(self, chunk_id: str):
        """Delete a specific chunk"""
        chunk_key = f"{self.chunk_prefix}{chunk_id}"
        self.redis_client.delete(chunk_key)
        logger.info(f"Deleted chunk: {chunk_id}")


# Global Redis client instance
redis_store = RedisVectorStore() 