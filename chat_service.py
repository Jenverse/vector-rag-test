import openai
from typing import List, Dict, Any, Optional
import logging
from config import settings
from redis_client import redis_store
from embedding_service import embedding_service

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = openai.OpenAI(api_key=settings.openai_api_key)


class ChatService:
    def __init__(self):
        """Initialize the chat service."""
        self.model = settings.chat_model
        self.max_context_tokens = 4000  # Leave room for response
        self.system_prompt = """You are a helpful AI assistant that answers questions based on the provided context from documents. 

Instructions:
1. Answer questions using ONLY the information provided in the context
2. If the context doesn't contain enough information to answer the question, say so clearly
3. Always cite your sources by referencing the document names and sections when possible
4. Be concise but comprehensive in your answers
5. If multiple documents contain relevant information, synthesize the information clearly

Context format:
Each piece of context will include:
- Text content
- Source document name
- Document ID and chunk ID for reference"""

    def retrieve_context(
        self, 
        query: str, 
        top_k: int = None, 
        use_hybrid_search: bool = True
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context for a query."""
        try:
            # Generate query embedding
            query_embedding = embedding_service.get_query_embedding(query)
            
            # Use configured top_k or default
            if top_k is None:
                top_k = settings.top_k_results
            
            # Retrieve context using hybrid search
            if use_hybrid_search:
                context_chunks = redis_store.hybrid_search(
                    query_embedding=query_embedding,
                    text_query=query,
                    top_k=top_k
                )
            else:
                # Pure vector search
                context_chunks = redis_store.vector_search(
                    query_embedding=query_embedding,
                    top_k=top_k
                )
            
            logger.info(f"Retrieved {len(context_chunks)} context chunks for query")
            return context_chunks
            
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            return []
    
    def format_context(self, context_chunks: List[Dict[str, Any]]) -> str:
        """Format context chunks for the LLM prompt."""
        if not context_chunks:
            return "No relevant context found."
        
        formatted_context = []
        
        for i, chunk in enumerate(context_chunks, 1):
            source = chunk.get('filename', 'Unknown')
            doc_id = chunk.get('doc_id', 'unknown')
            chunk_id = chunk.get('chunk_id', 'unknown')
            text = chunk.get('text', '')
            source_url = chunk.get('source_url', '')
            
            context_entry = f"""
Document {i}:
Source: {source}
Reference: {doc_id}:{chunk_id}
URL: {source_url if source_url else 'N/A'}
Content: {text}
---"""
            formatted_context.append(context_entry)
        
        return "\n".join(formatted_context)
    
    def generate_response(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate a response using OpenAI Chat API."""
        try:
            # Format context
            formatted_context = self.format_context(context_chunks)
            
            # Create messages for the chat completion
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"""
Context:
{formatted_context}

Question: {query}

Please provide a comprehensive answer based on the context provided above. Include specific references to the source documents when possible."""}
            ]
            
            # Generate response
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temperature for more factual responses
                max_tokens=1000
            )
            
            # Extract response content
            answer = response.choices[0].message.content
            
            # Prepare source information
            sources = []
            for chunk in context_chunks:
                source_info = {
                    "doc_id": chunk.get('doc_id'),
                    "chunk_id": chunk.get('chunk_id'),
                    "filename": chunk.get('filename'),
                    "source_url": chunk.get('source_url', ''),
                    "relevance_score": chunk.get('score', chunk.get('combined_score', 0)),
                    "text_snippet": chunk.get('text', '')[:200] + "..." if len(chunk.get('text', '')) > 200 else chunk.get('text', '')
                }
                sources.append(source_info)
            
            result = {
                "answer": answer,
                "sources": sources,
                "query": query,
                "context_count": len(context_chunks),
                "model_used": self.model
            }
            
            logger.info(f"Generated response for query: {query[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "answer": f"I apologize, but I encountered an error while generating a response: {str(e)}",
                "sources": [],
                "query": query,
                "context_count": 0,
                "model_used": self.model,
                "error": str(e)
            }
    
    def chat(
        self, 
        query: str, 
        top_k: int = None, 
        use_hybrid_search: bool = True
    ) -> Dict[str, Any]:
        """Complete chat workflow: retrieve context and generate response."""
        try:
            # Retrieve relevant context
            context_chunks = self.retrieve_context(
                query=query, 
                top_k=top_k, 
                use_hybrid_search=use_hybrid_search
            )
            
            # Generate response
            response = self.generate_response(query, context_chunks)
            
            return response
            
        except Exception as e:
            logger.error(f"Error in chat workflow: {str(e)}")
            return {
                "answer": f"I apologize, but I encountered an error: {str(e)}",
                "sources": [],
                "query": query,
                "context_count": 0,
                "model_used": self.model,
                "error": str(e)
            }
    
    def get_chat_history_summary(self, messages: List[Dict[str, str]]) -> str:
        """Generate a summary of chat history for context."""
        try:
            # Format recent messages
            history_text = []
            for msg in messages[-5:]:  # Last 5 messages
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                history_text.append(f"{role.title()}: {content}")
            
            history_string = "\n".join(history_text)
            
            # Generate summary if history is long
            if len(history_string) > 500:
                summary_prompt = f"""Summarize this conversation history in 2-3 sentences:

{history_string}

Summary:"""
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": summary_prompt}],
                    temperature=0.3,
                    max_tokens=150
                )
                
                return response.choices[0].message.content
            
            return history_string
            
        except Exception as e:
            logger.error(f"Error generating chat history summary: {str(e)}")
            return ""
    
    def contextual_chat(
        self, 
        query: str, 
        chat_history: List[Dict[str, str]] = None,
        top_k: int = None
    ) -> Dict[str, Any]:
        """Chat with conversation context."""
        try:
            # Enhance query with chat history if provided
            enhanced_query = query
            if chat_history:
                history_summary = self.get_chat_history_summary(chat_history)
                if history_summary:
                    enhanced_query = f"""
Previous conversation context:
{history_summary}

Current question: {query}
"""
            
            # Use the enhanced query for context retrieval
            context_chunks = self.retrieve_context(enhanced_query, top_k)
            
            # Generate response with original query but enhanced context
            response = self.generate_response(query, context_chunks)
            
            return response
            
        except Exception as e:
            logger.error(f"Error in contextual chat: {str(e)}")
            return self.chat(query, top_k)


# Global chat service instance
chat_service = ChatService() 