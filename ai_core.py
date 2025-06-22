import re
import logging
import google.generativeai as genai
from typing import Dict, Optional, Tuple
import io
from PIL import Image
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Language patterns and keywords
LANGUAGE_PATTERNS = {
    'english': {
        'keywords': ['hello', 'hi', 'what', 'how', 'why', 'when', 'where', 'who', 'can you', 'please', 'thank you', 'analyze', 'explain'],
        'patterns': [r'\bthe\b', r'\band\b', r'\bor\b', r'\bof\b', r'\bin\b', r'\bis\b', r'\bare\b']
    },
    'spanish': {
        'keywords': ['hola', 'qué', 'cómo', 'por qué', 'cuándo', 'dónde', 'quién', 'puedes', 'por favor', 'gracias'],
        'patterns': [r'\bel\b', r'\bla\b', r'\by\b', r'\bde\b', r'\ben\b', r'\bes\b']
    },
    'french': {
        'keywords': ['bonjour', 'qu\'est-ce que', 'comment', 'pourquoi', 'quand', 'où', 'qui', 'pouvez-vous', 'merci'],
        'patterns': [r'\ble\b', r'\bla\b', r'\bet\b', r'\bde\b', r'\best\b']
    },
    'german': {
        'keywords': ['hallo', 'was', 'wie', 'warum', 'wann', 'wo', 'wer', 'können sie', 'danke'],
        'patterns': [r'\bder\b', r'\bdie\b', r'\bdas\b', r'\bund\b', r'\bist\b']
    },
    'japanese': {
        'keywords': ['こんにちは', 'ありがとう', 'なに', 'どう', 'なぜ', 'いつ', 'どこ'],
        'patterns': [r'[ひらがな]', r'[カタカナ]', r'です', r'ます']
    },
    'korean': {
        'keywords': ['안녕하세요', '감사합니다', '무엇', '어떻게', '왜', '언제', '어디서'],
        'patterns': [r'[가-힣]', r'입니다', r'습니다']
    },
    'chinese': {
        'keywords': ['你好', '谢谢', '什么', '怎么', '为什么', '什么时候', '哪里'],
        'patterns': [r'[一-龯]', r'的', r'了', r'是']
    },
    'arabic': {
        'keywords': ['مرحبا', 'شكرا', 'ماذا', 'كيف', 'لماذا', 'متى', 'أين'],
        'patterns': [r'[ا-ي]', r'في', r'من']
    },
    'indonesian': {
        'keywords': ['halo', 'apa', 'bagaimana', 'mengapa', 'kapan', 'dimana', 'siapa', 'tolong', 'terima kasih'],
        'patterns': [r'\byang\b', r'\bdan\b', r'\bdi\b', r'\badalah\b']
    }
}

class AICore:
    """Unified AI core for language detection, intent analysis, and response generation."""
    
    def __init__(self):
        # Initialize Gemini
        self.api_key = GEMINI_API_KEY
        self.text_model = None
        self.vision_model = None
        self.model_name = "gemini-2.0-flash-exp"  # Default model name
        self._initialize_models()
        
        # Intent patterns
        self.intent_patterns = {
            'detailed_explanation': {
                'patterns': [
                    r'(jelaskan|explain|expliquer|erklären|説明|설명|解释|اشرح)',
                    r'(bagaimana|how|comment|wie|どうやって|어떻게|怎么|كيف)',
                    r'(mengapa|why|pourquoi|warum|なぜ|왜|为什么|لماذا)',
                    r'(analisa|analyze|analyser|analysieren|分析|분석|تحليل)',
                    r'(detail|detailed|détaillé|detailliert|詳細|자세히|详细|تفصيلي)',
                    r'(tutorial|guide|panduan|anleitung|ガイド|가이드|指南|دليل)'
                ],
                'weight': 2
            },
            'simple_question': {
                'patterns': [
                    r'^(apa|what|qu\'?est|was|何|무엇|什么|ما)\s',
                    r'^(siapa|who|qui|wer|誰|누구|谁|من)\s',
                    r'^(kapan|when|quand|wann|いつ|언제|什么时候|متى)\s',
                    r'^(dimana|where|où|wo|どこ|어디|哪里|أين)\s',
                    r'^(apakah|is|est|ist|ですか|입니까|是|هل)',
                    r'(ya\?|no\?|yes\?|benar\?|true\?|정말\?|真的\?|صحيح\?)'
                ],
                'weight': 3
            },
            'urgent_help': {
                'patterns': [
                    r'(urgent|mendesak|tolong|help|aide|hilfe|助けて|도와주세요|帮助|مساعدة)',
                    r'(cepat|quick|vite|schnell|早く|빨리|快|بسرعة)'
                ],
                'weight': 2
            },
            'greeting': {
                'patterns': [
                    r'^(hai|halo|hello|hi|salut|hallo|こんにちは|안녕|你好|مرحبا)',
                    r'(selamat|good|bon|guten|おはよう|안녕하세요|早上好|صباح الخير)'
                ],
                'weight': 1
            }
        }
        
        # Command patterns
        self.command_patterns = {
            'help': [r'(bantuan|help|aide|hilfe|ヘルプ|도움|帮助|مساعدة)', r'(perintah|commands|commandes|befehle)'],
            'clear_conversation': [r'(hapus.*percakapan|clear.*conversation)', r'(reset.*chat|mulai.*baru)'],
            'settings': [r'(pengaturan|settings|paramètres|einstellungen|設定|설정|设置|إعدادات)']
        }
        
        # Language instructions
        self.lang_instructions = {
            'indonesian': "Respond in Bahasa Indonesia.",
            'english': "Respond in English.",
            'spanish': "Responde en Español.",
            'french': "Répondez en Français.",
            'german': "Antworten Sie auf Deutsch.",
            'japanese': "日本語で返答してください。",
            'korean': "한국어로 답변해주세요.",
            'chinese': "请用中文回答。",
            'arabic': "أجب باللغة العربية."
        }
    
    def _initialize_models(self):
        """Initialize AI models."""
        try:
            if not self.api_key or self.api_key == "your_gemini_api_key_here":
                logger.error("Invalid or missing Gemini API key")
                return
            
            genai.configure(api_key=self.api_key)
            
            # Initialize text model
            self.model_name = "gemini-2.5-pro"  # Set the actual model name
            self.text_model = genai.GenerativeModel(self.model_name)
            
            # Initialize vision model (same model for both text and vision)
            self.vision_model = self.text_model
            
            logger.info(f"AI models initialized successfully with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.text_model = None
            self.vision_model = None
    
    def detect_language(self, text: str) -> Tuple[str, float]:
        """Detect language of input text."""
        if not text or not text.strip():
            return 'indonesian', 0.5
        
        text_lower = text.lower().strip()
        scores = {}
        
        for lang, data in LANGUAGE_PATTERNS.items():
            score = 0
            
            # Check keywords
            for keyword in data['keywords']:
                if keyword.lower() in text_lower:
                    score += 2
            
            # Check patterns
            for pattern in data['patterns']:
                matches = len(re.findall(pattern, text_lower))
                score += matches
            
            if len(text_lower) > 0:
                scores[lang] = score / len(text_lower.split())
        
        if not scores:
            return 'indonesian', 0.5
        
        best_lang = max(scores, key=scores.get)
        confidence = min(scores[best_lang], 1.0)
        
        if confidence < 0.1:
            return 'indonesian', 0.5
        
        return best_lang, confidence
    
    def analyze_intent(self, message: str, language: str = None) -> Dict:
        """Analyze user intent and determine response requirements."""
        if not message:
            return self._default_intent()
        
        if not language:
            language, confidence = self.detect_language(message)
        else:
            confidence = 0.8
        
        message_lower = message.lower().strip()
        
        # Calculate intent scores
        intent_scores = {}
        for intent_type, data in self.intent_patterns.items():
            score = 0
            for pattern in data['patterns']:
                matches = len(re.findall(pattern, message_lower, re.IGNORECASE))
                score += matches * data['weight']
            intent_scores[intent_type] = score
        
        primary_intent = max(intent_scores, key=intent_scores.get) if max(intent_scores.values()) > 0 else 'general'
        complexity = self._get_complexity(message_lower)
        response_style = self._get_response_style(primary_intent, complexity)
        
        return {
            'language': language,
            'confidence': confidence,
            'primary_intent': primary_intent,
            'complexity': complexity,
            'response_style': response_style,
            'message_length': len(message.split()),
            'has_question_mark': '?' in message
        }
    
    def detect_command(self, message: str) -> Optional[Dict]:
        """Detect if message contains a command."""
        if not message:
            return None
        
        message_lower = message.lower().strip()
        
        # Handle explicit commands
        if message.startswith('/'):
            command_part = message[1:].split()[0].lower()
            explicit_mapping = {
                'help': 'help', 'bantuan': 'help',
                'clearconversation': 'clear_conversation', 'clear': 'clear_conversation',
                'settings': 'settings', 'pengaturan': 'settings'
            }
            command_type = explicit_mapping.get(command_part)
            if command_type:
                return {'command': command_type, 'confidence': 1.0, 'explicit': True}
            return None
        
        # Handle natural language commands
        detected_lang, _ = self.detect_language(message)
        
        for command_type, patterns in self.command_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    score += 2
            
            if re.search(r'(bot|kamu|you|assistant)', message_lower, re.IGNORECASE):
                score += 1
            
            if score >= 2:
                return {
                    'command': command_type,
                    'confidence': min(score / 4.0, 1.0),
                    'language': detected_lang,
                    'explicit': False
                }
        
        return None
    
    def get_response_prompt(self, intent_analysis: Dict, is_image: bool = False) -> str:
        """Generate response prompt based on intent analysis."""
        style = intent_analysis['response_style']
        
        length_instructions = {
            'short': "Give a brief, direct answer in 1-2 sentences.",
            'medium': "Provide a clear, informative response in 2-4 sentences.",
            'long': "Give a comprehensive explanation with details and examples."
        }
        
        base_instruction = self.lang_instructions.get(intent_analysis['language'], self.lang_instructions['indonesian'])
        
        prompt = f"{base_instruction}\n\n"
        prompt += f"RESPONSE STYLE:\n"
        prompt += f"- Length: {length_instructions[style['length']]}\n"
        prompt += f"- Tone: {style['tone'].title()}\n"
        
        intent = intent_analysis['primary_intent']
        if intent == 'detailed_explanation':
            prompt += "\nPROVIDE DETAILED EXPLANATION with background context."
        elif intent == 'simple_question':
            prompt += "\nANSWER DIRECTLY and concisely."
        elif intent == 'urgent_help':
            prompt += "\nPRIORITIZE immediate, actionable assistance."
        
        if is_image:
            prompt += f"\n\nFor image analysis: Provide a {style['length']} description focusing on relevant aspects."
        
        return prompt
    
    async def generate_response(self, message: str, user_context: dict = None, conversation_history: list = None) -> Optional[str]:
        """Generate intelligent response."""
        if not self.text_model:
            return None

        try:
            # Check for commands first
            command_info = self.detect_command(message)
            if command_info and command_info['confidence'] > 0.6:
                suggestions = {
                    'help': "Gunakan /help untuk melihat bantuan lengkap",
                    'clear_conversation': "Gunakan /clearconversation untuk menghapus riwayat",
                    'settings': "Gunakan /conversation untuk pengaturan percakapan"
                }
                suggestion = suggestions.get(command_info['command'])
                if suggestion:
                    return suggestion
            
            # Analyze intent and generate response
            intent_analysis = self.analyze_intent(message)
            style_prompt = self.get_response_prompt(intent_analysis, False)
            
            system_prompt = self._build_system_prompt(intent_analysis, style_prompt, user_context)
            conversation_context = self._build_conversation_context(conversation_history)
            
            full_prompt = f"{system_prompt}{conversation_context}\n\nUser Message: {message}"
            response = self.text_model.generate_content(full_prompt)
            
            generated_text = response.text.strip() if response and response.text else None
            return self._post_process_response(generated_text, intent_analysis) if generated_text else None
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    async def analyze_image(self, image_data: bytes, caption: str = None, user_context: dict = None) -> Optional[str]:
        """Analyze image with intelligent context understanding."""
        if not self.vision_model:
            return None

        try:
            # Process image
            image = self._process_image(image_data)
            if not image:
                return None
            
            # Analyze intent
            intent_analysis = self.analyze_intent(caption) if caption else {
                'language': 'indonesian', 'primary_intent': 'general', 'complexity': 'medium',
                'response_style': {'length': 'medium', 'tone': 'friendly', 'format': 'paragraph'}
            }
            
            # Generate response
            style_prompt = self.get_response_prompt(intent_analysis, True)
            system_prompt = self._build_vision_system_prompt(intent_analysis, style_prompt, user_context)
            
            content_parts = [
                f"{system_prompt}\n\n{'User question: ' + caption if caption else 'Analyze this image:'}",
                image
            ]
            
            response = self.vision_model.generate_content(content_parts)
            generated_text = response.text.strip() if response and response.text else None
            
            return self._post_process_response(generated_text, intent_analysis) if generated_text else None
            
        except Exception as e:
            logger.error(f"Gemini Vision API error: {e}")
            return None
    
    def _get_complexity(self, message: str) -> str:
        """Determine message complexity."""
        if re.search(r'(mengapa|why|bagaimana|how|jelaskan|explain|analisa|analyze)', message, re.IGNORECASE):
            return 'high'
        if re.search(r'^(ya|no|yes|ok|terima kasih|thanks)$', message, re.IGNORECASE):
            return 'low'
        return 'medium'
    
    def _get_response_style(self, intent: str, complexity: str) -> Dict:
        """Determine response style."""
        style = {'length': 'medium', 'tone': 'friendly', 'format': 'paragraph'}
        
        if intent == 'detailed_explanation':
            style.update({'length': 'long', 'format': 'structured'})
        elif intent == 'simple_question':
            style['length'] = 'short'
        elif intent == 'urgent_help':
            style.update({'length': 'medium', 'tone': 'helpful'})
        elif intent == 'greeting':
            style['length'] = 'short'
        
        if complexity == 'high' and style['length'] == 'short':
            style['length'] = 'medium'
        elif complexity == 'low':
            style['length'] = 'short'
        
        return style
    
    def _default_intent(self) -> Dict:
        """Return default intent analysis."""
        return {
            'language': 'indonesian',
            'confidence': 0.5,
            'primary_intent': 'general',
            'complexity': 'medium',
            'response_style': {'length': 'medium', 'tone': 'friendly', 'format': 'paragraph'},
            'message_length': 0,
            'has_question_mark': False
        }
    
    def _process_image(self, image_data: bytes):
        """Process image data to PIL Image."""
        try:
            image = Image.open(io.BytesIO(image_data))
            if image.mode != 'RGB':
                if image.mode == 'RGBA':
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[-1])
                    image = background
                else:
                    image = image.convert('RGB')
            return image
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return None
    
    def _build_system_prompt(self, intent_analysis: dict, style_prompt: str, user_context: dict = None) -> str:
        """Build system prompt for text generation."""
        prompt = f"""You are an intelligent AI assistant that adapts to user needs.

INTENT ANALYSIS:
- Language: {intent_analysis['language']}
- Intent: {intent_analysis['primary_intent']}
- Complexity: {intent_analysis['complexity']}

RULES:
- NEVER start with "Tentu", "Sure", "Certainly" in any language
- NEVER use robot emoji 🤖
- Use appropriate emoji that matches the topic
- Be accurate and factual
- ALWAYS respond in the detected language

{style_prompt}"""
        
        if user_context:
            prompt += f"\nUser: {user_context.get('first_name', 'User')}"
            if user_context.get('is_admin'):
                prompt += " (Admin)"
        
        return prompt
    
    def _build_vision_system_prompt(self, intent_analysis: dict, style_prompt: str, user_context: dict = None) -> str:
        """Build system prompt for image analysis."""
        prompt = f"""You are an expert AI for image analysis.

INTENT ANALYSIS:
- Language: {intent_analysis['language']}
- Intent: {intent_analysis['primary_intent']}

RULES:
- NEVER use "Tentu", "Sure", "Certainly" at the start
- NEVER use robot emoji 🤖
- Identify objects, people, activities, and context
- Use relevant emoji that match the image content
- ALWAYS respond in the detected language

{style_prompt}"""
        
        if user_context:
            prompt += f"\nUser: {user_context.get('first_name', 'User')}"
        
        return prompt
    
    def _build_conversation_context(self, conversation_history: list) -> str:
        """Build conversation context string."""
        if not conversation_history:
            return ""
        
        context = "\n\nPrevious Conversation:\n"
        for msg in conversation_history[-5:]:
            context += f"User: {msg['message_text']}\n"
            context += f"Assistant: {msg['response_text']}\n\n"
        
        return context + "Use this context for relevant responses."
    
    def _post_process_response(self, text: str, intent_analysis: dict) -> str:
        """Post-process response to clean up unwanted patterns."""
        if not text:
            return text
        
        # Remove forbidden starting words
        forbidden_starts = ['tentu', 'tentunya', 'sure', 'certainly', 'por supuesto', 'bien sûr']
        for forbidden in forbidden_starts:
            if text.lower().startswith(forbidden.lower()):
                sentences = text.split('.')
                if len(sentences) > 1:
                    text = '.'.join(sentences[1:]).strip()
                    if text.startswith('.'):
                        text = text[1:].strip()
                break
        
        # Remove robot emoji and clean up
        text = text.replace('🤖', '')
        text = ' '.join(text.split())
        
        # Adjust length for short responses
        if intent_analysis['response_style']['length'] == 'short':
            sentences = text.split('.')
            if len(sentences) > 2:
                text = '. '.join(sentences[:2]) + '.'
        
        return text
    
    def is_available(self) -> bool:
        """Check if text model is available."""
        return self.text_model is not None
    
    def is_vision_available(self) -> bool:
        """Check if vision model is available."""
        return self.vision_model is not None

# Global instance
ai_core = AICore()
