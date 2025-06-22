import logging
import google.generativeai as genai
from typing import Optional, Union
import io
from PIL import Image
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        """Initialize Gemini client."""
        self.api_key = GEMINI_API_KEY
        self.text_model = None
        self.vision_model = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Gemini client."""
        try:
            if not self.api_key or self.api_key == "your_gemini_api_key_here":
                logger.error("Invalid or missing Gemini API key")
                return
            
            genai.configure(api_key=self.api_key)
            # Use Gemini 1.5 Flash for both text and vision
            self.text_model = genai.GenerativeModel('gemini-2.5-pro')
            self.vision_model = genai.GenerativeModel('gemini-2.5-pro')
            logger.info("Gemini client initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.text_model = None
            self.vision_model = None
    
    async def generate_response(self, message: str, user_context: dict = None, conversation_history: list = None) -> Optional[str]:
        """Generate response using Gemini with conversation context."""
        if not self.text_model:
            return None
        
        try:
            system_prompt = """Kamu adalah asisten AI yang ramah dan membantu. 
Berikan respons yang natural, informatif, dan engaging.

ATURAN WAJIB:
- JANGAN PERNAH mulai respons dengan kata "Tentu" atau "Tentunya"
- JANGAN gunakan emoji robot (🤖) sama sekali
- JANGAN ulangi sapaan seperti "Halo" kecuali user baru menyapa
- Langsung berikan jawaban atau tanggapan yang relevan
- Gunakan emoji yang sesuai topik (tapi hindari robot emoji)
- Berikan respons yang akurat dan faktual
- Jika tidak yakin, katakan dengan jujur

CONTOH YANG SALAH:
❌ "Tentu! Jawaban 1+1 adalah 2"
❌ "🤖 Halo! Saya akan membantu"

CONTOH YANG BENAR:
✅ "1+1 sama dengan 2 😊"
✅ "Hasil perhitungan 1+1 adalah 2 📝"
✅ "Jawabannya adalah 2! 🔢"

Selalu berikan jawaban yang akurat dan faktual, jangan setuju dengan informasi yang salah."""
            
            if user_context:
                context_info = f"\nUser: {user_context.get('first_name', 'User')}"
                if user_context.get('is_admin'):
                    context_info += " (Admin)"
                system_prompt += context_info
            
            # Build conversation context
            conversation_context = ""
            if conversation_history:
                conversation_context = "\n\nPercakapan sebelumnya:\n"
                for i, msg in enumerate(conversation_history[-5:], 1):  # Last 5 messages
                    conversation_context += f"User: {msg['message_text']}\n"
                    conversation_context += f"Bot: {msg['response_text']}\n\n"
                conversation_context += "Gunakan konteks ini untuk memberikan respons yang lebih relevan."
            
            full_prompt = f"{system_prompt}{conversation_context}\n\nPesan user: {message}"
            response = self.text_model.generate_content(full_prompt)
            
            generated_text = response.text.strip() if response and response.text else None
            
            # Post-process to remove forbidden patterns
            if generated_text:
                # Remove "Tentu" at the beginning
                if generated_text.lower().startswith('tentu'):
                    # Find the first sentence end and remove everything before it
                    sentences = generated_text.split('.')
                    if len(sentences) > 1:
                        generated_text = '.'.join(sentences[1:]).strip()
                        if generated_text.startswith('.'):
                            generated_text = generated_text[1:].strip()
                
                # Remove robot emoji
                generated_text = generated_text.replace('🤖', '')
                
                # Clean up any double spaces
                generated_text = ' '.join(generated_text.split())
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    async def analyze_image(self, image_data: bytes, caption: str = None, user_context: dict = None) -> Optional[str]:
        """Analyze image using Gemini Vision model."""
        if not self.vision_model:
            logger.error("Vision model not available")
            return None
        
        try:
            # Convert image data to PIL Image
            image = Image.open(io.BytesIO(image_data))
            logger.info(f"Processing image for analysis: {image.size}, {image.mode}")
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                if image.mode == 'RGBA':
                    # Create white background for transparent images
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[-1])
                    image = background
                else:
                    image = image.convert('RGB')
                logger.info("Converted image to RGB mode")
            
            # Prepare system prompt
            system_prompt = """Kamu adalah AI yang ahli menganalisis gambar dalam bahasa Indonesia.

ATURAN WAJIB:
- JANGAN gunakan kata "Tentu" di awal respons
- JANGAN gunakan emoji robot 🤖
- Berikan analisis yang detail dan informatif
- Identifikasi objek, hewan, aktivitas, atau situasi dalam gambar
- Jika ada teks dalam gambar, baca dan sertakan
- Jawab pertanyaan user tentang gambar dengan akurat
- Gunakan emoji yang relevan dengan konten gambar"""
            
            if user_context:
                system_prompt += f"\nUser: {user_context.get('first_name', 'User')}"
            
            # Create content list for the model
            content_parts = []
            
            if caption and caption.strip():
                content_parts.append(f"{system_prompt}\n\nPertanyaan user tentang gambar: {caption}\n\nAnalisis gambar dan jawab pertanyaan user:")
            else:
                content_parts.append(f"{system_prompt}\n\nAnalisis gambar ini secara detail:")
            
            content_parts.append(image)
            
            logger.info("Sending image to Gemini Vision API...")
            response = self.vision_model.generate_content(content_parts)
            
            if not response or not response.text:
                logger.error("No response from Gemini Vision API")
                return None
            
            generated_text = response.text.strip()
            logger.info(f"Received response from Gemini Vision: {len(generated_text)} characters")
            
            # Post-process to remove forbidden patterns
            if generated_text:
                # Remove "Tentu" at the beginning
                if generated_text.lower().startswith('tentu'):
                    sentences = generated_text.split('.')
                    if len(sentences) > 1:
                        generated_text = '.'.join(sentences[1:]).strip()
                        if generated_text.startswith('.'):
                            generated_text = generated_text[1:].strip()
                
                # Remove robot emoji
                generated_text = generated_text.replace('🤖', '')
                
                # Clean up spaces
                generated_text = ' '.join(generated_text.split())
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Gemini Vision API error: {str(e)}")
            # Log more details for debugging
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    def is_available(self) -> bool:
        """Check if Gemini model is available."""
        return self.text_model is not None
    
    def is_vision_available(self) -> bool:
        """Check if Gemini Vision model is available."""
        return self.vision_model is not None

# Global instance
gemini_client = GeminiClient()
