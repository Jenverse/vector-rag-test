import os
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple
from unstructured.partition.auto import partition
from unstructured.chunking.title import chunk_by_title
from unstructured.cleaners.core import clean_extra_whitespace
import logging
from config import settings

# Download required NLTK data with SSL fix
try:
    import nltk
    import ssl
    
    # Handle SSL certificate issues
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
    
    # Download required data with fallback
    try:
        nltk.download('punkt_tab', quiet=True)
    except:
        try:
            nltk.download('punkt', quiet=True)
        except:
            pass
    
    try:
        nltk.download('averaged_perceptron_tagger_eng', quiet=True)
    except:
        try:
            nltk.download('averaged_perceptron_tagger', quiet=True)
        except:
            pass
            
except Exception as e:
    logging.warning(f"Could not download NLTK data: {e}")

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self):
        """Initialize the document processor."""
        self.max_chunk_size = settings.max_chunk_size
        self.chunk_overlap = settings.chunk_overlap
        self.supported_extensions = {'.pdf', '.docx', '.md', '.txt', '.gdoc'}
    
    def generate_doc_id(self, content: str, source_url: str = "") -> str:
        """Generate a unique document ID based on content and source."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        source_hash = hashlib.md5(source_url.encode()).hexdigest()
        return f"{source_hash}_{content_hash}_{int(time.time())}"[:32]
    
    def is_supported_file(self, filename: str) -> bool:
        """Check if file type is supported."""
        return any(filename.lower().endswith(ext) for ext in self.supported_extensions)
    
    def extract_text_from_file(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from a file using unstructured.io."""
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Use unstructured to partition the document
            elements = partition(filename=file_path)
            
            # Extract text from elements
            text_content = []
            metadata = {
                "filename": os.path.basename(file_path),
                "file_size": os.path.getsize(file_path),
                "last_modified": os.path.getmtime(file_path),
                "elements_count": len(elements)
            }
            
            for element in elements:
                if hasattr(element, 'text') and element.text.strip():
                    # Clean extra whitespace
                    cleaned_text = clean_extra_whitespace(element.text)
                    text_content.append(cleaned_text)
            
            full_text = "\n\n".join(text_content)
            logger.info(f"Extracted {len(full_text)} characters from {file_path}")
            
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            raise e
    
    def extract_text_from_url(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from a URL (for Google Docs, etc.)."""
        try:
            logger.info(f"Processing URL: {url}")
            
            # Use unstructured to partition from URL
            elements = partition(url=url)
            
            # Extract text from elements
            text_content = []
            metadata = {
                "source_url": url,
                "last_modified": time.time(),
                "elements_count": len(elements)
            }
            
            for element in elements:
                if hasattr(element, 'text') and element.text.strip():
                    # Clean extra whitespace
                    cleaned_text = clean_extra_whitespace(element.text)
                    text_content.append(cleaned_text)
            
            full_text = "\n\n".join(text_content)
            logger.info(f"Extracted {len(full_text)} characters from URL")
            
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"Error extracting text from URL {url}: {str(e)}")
            raise e
    
    def chunk_text(self, text: str, doc_id: str) -> List[Dict[str, Any]]:
        """Chunk text into smaller pieces."""
        try:
            # Create elements for chunking
            from unstructured.documents.elements import NarrativeText
            
            # Split text into paragraphs first
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            elements = [NarrativeText(text=p) for p in paragraphs]
            
            # Chunk using unstructured's chunking strategy
            chunked_elements = chunk_by_title(
                elements,
                max_characters=self.max_chunk_size,
                overlap=self.chunk_overlap
            )
            
            # Convert to our chunk format
            chunks = []
            for i, element in enumerate(chunked_elements):
                if hasattr(element, 'text') and element.text.strip():
                    chunk = {
                        "doc_id": doc_id,
                        "chunk_id": f"chunk_{i}",
                        "text": element.text.strip(),
                        "chunk_index": i,
                        "chunk_size": len(element.text)
                    }
                    chunks.append(chunk)
            
            logger.info(f"Created {len(chunks)} chunks for document {doc_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking text for {doc_id}: {str(e)}")
            # Fallback to simple chunking
            return self._simple_chunk_text(text, doc_id)
    
    def _simple_chunk_text(self, text: str, doc_id: str) -> List[Dict[str, Any]]:
        """Simple fallback chunking method."""
        chunks = []
        words = text.split()
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 for space
            
            if current_size + word_size > self.max_chunk_size and current_chunk:
                # Create chunk
                chunk_text = " ".join(current_chunk)
                chunk = {
                    "doc_id": doc_id,
                    "chunk_id": f"chunk_{len(chunks)}",
                    "text": chunk_text,
                    "chunk_index": len(chunks),
                    "chunk_size": len(chunk_text)
                }
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_words = int(len(current_chunk) * (self.chunk_overlap / self.max_chunk_size))
                current_chunk = current_chunk[-overlap_words:] if overlap_words > 0 else []
                current_size = sum(len(w) + 1 for w in current_chunk)
            
            current_chunk.append(word)
            current_size += word_size
        
        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunk = {
                "doc_id": doc_id,
                "chunk_id": f"chunk_{len(chunks)}",
                "text": chunk_text,
                "chunk_index": len(chunks),
                "chunk_size": len(chunk_text)
            }
            chunks.append(chunk)
        
        return chunks
    
    def process_file(self, file_path: str, source_url: str = "") -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """Process a file: extract text, generate doc_id, and create chunks."""
        try:
            # Extract text and metadata
            text, metadata = self.extract_text_from_file(file_path)
            
            # Generate document ID
            doc_id = self.generate_doc_id(text, source_url)
            
            # Create chunks
            chunks = self.chunk_text(text, doc_id)
            
            # Add metadata to chunks
            for chunk in chunks:
                chunk.update({
                    "source_url": source_url,
                    "filename": metadata["filename"],
                    "last_modified": metadata["last_modified"]
                })
            
            logger.info(f"Successfully processed file {file_path}: {doc_id}")
            return doc_id, chunks, metadata
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            raise e
    
    def process_url(self, url: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """Process a URL: extract text, generate doc_id, and create chunks."""
        try:
            # Extract text and metadata
            text, metadata = self.extract_text_from_url(url)
            
            # Generate document ID
            doc_id = self.generate_doc_id(text, url)
            
            # Create chunks
            chunks = self.chunk_text(text, doc_id)
            
            # Add metadata to chunks
            for chunk in chunks:
                chunk.update({
                    "source_url": url,
                    "filename": f"url_doc_{doc_id}",
                    "last_modified": metadata["last_modified"]
                })
            
            logger.info(f"Successfully processed URL {url}: {doc_id}")
            return doc_id, chunks, metadata
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            raise e


# Global document processor instance
document_processor = DocumentProcessor() 