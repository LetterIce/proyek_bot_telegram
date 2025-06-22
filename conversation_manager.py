import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from database import db

logger = logging.getLogger(__name__)

class ConversationManager:
    """Manages conversation context and memory for users."""
    
    def __init__(self):
        self.context_cache = {}  # In-memory cache for recent contexts
        self.cache_timeout = 300  # 5 minutes
    
    def get_relevant_context(self, user_id: int, current_message: str, max_messages: int = 10) -> List[Dict]:
        """Get relevant conversation context based on current message."""
        try:
            # Get full conversation history
            full_history = db.get_conversation_context(user_id)
            
            if not full_history:
                return []
            
            # Simple relevance scoring based on keyword matching
            relevant_messages = []
            current_words = set(current_message.lower().split())
            
            for msg in full_history[-20:]:  # Check last 20 messages
                msg_words = set(msg['message_text'].lower().split())
                response_words = set(msg['response_text'].lower().split())
                
                # Calculate relevance score
                score = len(current_words.intersection(msg_words)) + \
                       len(current_words.intersection(response_words)) * 0.5
                
                if score > 0:
                    msg['relevance_score'] = score
                    relevant_messages.append(msg)
            
            # Sort by relevance and recency
            relevant_messages.sort(key=lambda x: (x['relevance_score'], x['timestamp']), reverse=True)
            
            # Return most relevant messages up to limit
            return relevant_messages[:max_messages]
            
        except Exception as e:
            logger.error(f"Error getting relevant context: {e}")
            return full_history[-max_messages:] if full_history else []
    
    def should_include_context(self, user_id: int, current_message: str) -> bool:
        """Determine if context should be included based on message type."""
        # Keywords that suggest continuation
        continuation_keywords = [
            'lanjut', 'selanjutnya', 'kemudian', 'terus', 'jadi', 'bagaimana',
            'mengapa', 'kenapa', 'itu', 'ini', 'yang tadi', 'sebelumnya',
            'seperti', 'sama', 'berbeda', 'bandingkan', 'jelaskan lebih'
        ]
        
        # Question words that might refer to previous context
        question_words = ['apa', 'siapa', 'kapan', 'dimana', 'mengapa', 'bagaimana']
        
        message_lower = current_message.lower()
        
        # Check for continuation indicators
        for keyword in continuation_keywords:
            if keyword in message_lower:
                return True
        
        # Check for questions that might need context
        for word in question_words:
            if word in message_lower and len(current_message.split()) <= 10:
                return True
        
        # Always include context for registered users unless it's a greeting
        greetings = ['halo', 'hai', 'selamat', 'hello', 'hi']
        if any(greeting in message_lower for greeting in greetings):
            return False
        
        return True
    
    def format_context_for_ai(self, context_messages: List[Dict]) -> str:
        """Format conversation context for AI prompt."""
        if not context_messages:
            return ""
        
        formatted_context = "\n=== Konteks Percakapan Sebelumnya ===\n"
        
        for i, msg in enumerate(context_messages, 1):
            timestamp = msg.get('timestamp', '')[:16]  # Show only date and time
            formatted_context += f"\n[{timestamp}] User: {msg['message_text']}\n"
            formatted_context += f"[{timestamp}] Bot: {msg['response_text']}\n"
        
        formatted_context += "\n=== Akhir Konteks ===\n"
        formatted_context += "Gunakan informasi di atas untuk memberikan respons yang lebih kontekstual dan relevan.\n"
        
        return formatted_context
    
    def clean_old_contexts(self, days_old: int = 30):
        """Clean up old conversation contexts (admin function)."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cutoff_str = cutoff_date.isoformat()
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM conversation_context WHERE timestamp < ?",
                    (cutoff_str,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleaned up {deleted_count} old conversation messages")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning old contexts: {e}")
            return 0

# Global conversation manager instance
conversation_manager = ConversationManager()
