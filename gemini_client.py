import logging
import google.generativeai as genai
from typing import Optional
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        """Initialize Gemini client."""
        self.api_key = GEMINI_API_KEY
        self.model = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Gemini client."""
        try:
            if not self.api_key or self.api_key == "your_gemini_api_key_here":
                logger.error("Invalid or missing Gemini API key")
                return
            
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-pro')
            logger.info("Gemini client initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.model = None
    
    async def generate_response(self, message: str, user_context: dict = None) -> Optional[str]:
        """Generate response using Gemini."""
        if not self.model:
            return None
        
        try:
            system_prompt = """Kamu adalah asisten bot Telegram yang ramah dan membantu. 
Berikan respons yang natural dan professional dalam bahasa Indonesia.
Jaga agar respons tetap singkat dan relevan.
Gunakan emoji yang sesuai untuk membuat percakapan lebih menarik.

PENTING:
- JANGAN gunakan kata "Tentu" di awal respons
- JANGAN ulangi sapaan seperti "Halo" kecuali ini adalah interaksi pertama
- JANGAN gunakan emoji robot 🤖 di awal atau dalam respons
- Langsung jawab pertanyaan atau tanggapi pesan user
- Berikan respons yang fokus dan to-the-point
- Gunakan emoji yang relevan dengan topik, tapi hindari emoji robot"""
            
            if user_context:
                context_info = f"\nInformasi user: {user_context.get('first_name', 'User')}"
                if user_context.get('is_admin'):
                    context_info += " (Admin)"
                if user_context.get('is_first_interaction'):
                    context_info += " - Ini adalah interaksi pertama user"
                system_prompt += context_info
            
            full_prompt = f"{system_prompt}\n\nPesan user: {message}"
            response = self.model.generate_content(full_prompt)
            
            return response.text.strip() if response and response.text else None
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Gemini model is available."""
        return self.model is not None

# Global instance
gemini_client = GeminiClient()
