import os
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple
import logging
from config import settings

logger = logging.getLogger(__name__)

# Lightweight document processing imports
try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("pypdf not available, PDF processing disabled")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not available, DOCX processing disabled")

try:
    # Use unstructured only as fallback, with minimal dependencies
    from unstructured.partition.auto import partition
    from unstructured.cleaners.core import clean_extra_whitespace
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    logger.warning("unstructured not available, using basic text processing")


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
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF using pypdf."""
        if not PDF_AVAILABLE:
            raise ImportError("pypdf not available for PDF processing")
        
        text_content = []
        with open(file_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text.strip():
                    text_content.append(text.strip())
        
        return "\n\n".join(text_content)
    
    def _extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX using python-docx."""
        if not DOCX_AVAILABLE:
            raise ImportError("python-docx not available for DOCX processing")
        
        doc = Document(file_path)
        text_content = []
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text.strip())
        
        return "\n\n".join(text_content)
    
    def _extract_text_file(self, file_path: str) -> str:
        """Extract text from plain text files."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def extract_text_from_file(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from a file using lightweight processors."""
        try:
            logger.info(f"Processing file: {file_path}")
            
            file_extension = os.path.splitext(file_path)[1].lower()
            text = ""
            
            # Use lightweight processors first
            if file_extension == '.pdf' and PDF_AVAILABLE:
                text = self._extract_pdf_text(file_path)
            elif file_extension == '.docx' and DOCX_AVAILABLE:
                text = self._extract_docx_text(file_path)
            elif file_extension in ['.txt', '.md']:
                text = self._extract_text_file(file_path)
            elif UNSTRUCTURED_AVAILABLE:
                # Fallback to unstructured with minimal strategy
                logger.info("Using unstructured as fallback")
                elements = partition(
                    filename=file_path,
                    strategy="fast",
                    include_page_breaks=False
                )
                
                text_content = []
                for element in elements:
                    if hasattr(element, 'text') and element.text.strip():
                        cleaned_text = clean_extra_whitespace(element.text)
                        text_content.append(cleaned_text)
                
                text = "\n\n".join(text_content)
            else:
                # Final fallback - try as text file
                text = self._extract_text_file(file_path)
            
            metadata = {
                "filename": os.path.basename(file_path),
                "file_size": os.path.getsize(file_path),
                "last_modified": os.path.getmtime(file_path),
                "processor": "lightweight"
            }
            
            logger.info(f"Extracted {len(text)} characters from {file_path}")
            return text, metadata
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            # Final fallback - try as text file
            try:
                text = self._extract_text_file(file_path)
                metadata = {
                    "filename": os.path.basename(file_path),
                    "file_size": len(text),
                    "last_modified": time.time(),
                    "processor": "fallback_text"
                }
                return text, metadata
            except:
                raise e
    
    def extract_text_from_url(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from a URL (for Google Docs, etc.)."""
        try:
            logger.info(f"Processing URL: {url}")
            
            if UNSTRUCTURED_AVAILABLE:
                # Use unstructured for URL processing
                elements = partition(
                    url=url,
                    strategy="fast",
                    include_page_breaks=False
                )
                
                text_content = []
                for element in elements:
                    if hasattr(element, 'text') and element.text.strip():
                        cleaned_text = clean_extra_whitespace(element.text)
                        text_content.append(cleaned_text)
                
                text = "\n\n".join(text_content)
            else:
                # Basic URL processing fallback
                import requests
                response = requests.get(url)
                response.raise_for_status()
                text = response.text
            
            metadata = {
                "source_url": url,
                "last_modified": time.time(),
                "processor": "url"
            }
            
            logger.info(f"Extracted {len(text)} characters from URL")
            return text, metadata
            
        except Exception as e:
            logger.error(f"Error extracting text from URL {url}: {str(e)}")
            raise e
    
    def chunk_text(self, text: str, doc_id: str) -> List[Dict[str, Any]]:
        """Chunk text into smaller pieces using simple sentence-based chunking."""
        try:
            chunks = []
            
            # Simple sentence-based chunking
            sentences = self._split_into_sentences(text)
            
            current_chunk = []
            current_size = 0
            
            for sentence in sentences:
                sentence_size = len(sentence) + 1  # +1 for space
                
                if current_size + sentence_size > self.max_chunk_size and current_chunk:
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
                    overlap_sentences = max(1, int(len(current_chunk) * 0.1))  # 10% overlap
                    current_chunk = current_chunk[-overlap_sentences:]
                    current_size = sum(len(s) + 1 for s in current_chunk)
                
                current_chunk.append(sentence)
                current_size += sentence_size
            
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
            
            logger.info(f"Created {len(chunks)} chunks for document {doc_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking text for {doc_id}: {str(e)}")
            # Fallback to word-based chunking
            return self._simple_word_chunk(text, doc_id)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Simple sentence splitting without NLTK."""
        sentences = []
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
                
            # Simple sentence splitting on periods, exclamation marks, question marks
            current_sentence = ""
            
            for char in paragraph:
                current_sentence += char
                if char in '.!?' and len(current_sentence.strip()) > 10:
                    # Check if it's likely end of sentence (not abbreviation)
                    if not self._is_abbreviation(current_sentence):
                        sentences.append(current_sentence.strip())
                        current_sentence = ""
            
            if current_sentence.strip():
                sentences.append(current_sentence.strip())
        
        return [s for s in sentences if s.strip()]
    
    def _is_abbreviation(self, sentence: str) -> bool:
        """Simple check for common abbreviations."""
        common_abbrevs = ['Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Prof.', 'Sr.', 'Jr.', 'Inc.', 'Ltd.', 'Co.', 'Corp.']
        sentence_end = sentence.strip()[-10:]  # Check last 10 characters
        return any(abbrev in sentence_end for abbrev in common_abbrevs)
    
    def _simple_word_chunk(self, text: str, doc_id: str) -> List[Dict[str, Any]]:
        """Simple word-based chunking fallback."""
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
                overlap_words = max(10, int(len(current_chunk) * 0.1))  # 10% overlap, min 10 words
                current_chunk = current_chunk[-overlap_words:]
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
        
        logger.info(f"Created {len(chunks)} chunks using word-based chunking for document {doc_id}")
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