import re
import logging
import google.generativeai as genai
from google import genai as google_genai
from google.genai import types
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
        self.grounding_client = None
        self.grounding_tool = None
        self.grounding_config = None
        self.model_name = "gemini-2.5-flash"  # Default model name
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
            },
            'current_events': {
                'patterns': [
                    r'(terbaru|latest|recent|atual|récent|aktuell|最新|최신|最近|أحدث)',
                    r'(sekarang|now|maintenant|jetzt|今|지금|现在|الآن)',
                    r'(hari ini|today|aujourd\'hui|heute|今日|오늘|今天|اليوم)',
                    r'(berita|news|nouvelles|nachrichten|ニュース|뉴스|新闻|أخبار)',
                    r'(kejadian|events|événements|ereignisse|イベント|사건|事件|أحداث)',
                    r'(siapa yang menang|who won|qui a gagné|wer hat gewonnen|誰が勝った|누가 이겼나|谁赢了|من فاز)',
                    r'(kapan|when|quand|wann|いつ|언제|什么时候|متى).*2024',
                    r'(euro 2024|olympics|world cup|election|pemilu)'
                ],
                'weight': 3
            },
            'factual_query': {
                'patterns': [
                    r'(berapa|how much|how many|combien|wie viel|いくら|얼마|多少|كم)',
                    r'(dimana|where|où|wo|どこ|어디|哪里|أين)',
                    r'(statistik|statistics|statistiques|statistiken|統計|통계|统计|إحصائيات)',
                    r'(data|données|daten|データ|데이터|数据|بيانات)',
                    r'(harga|price|prix|preis|価格|가격|价格|سعر)',
                    r'(populasi|population|einwohner|人口|인구|人口|سكان)',
                    r'(alamat|address|adresse|住所|주소|地址|عنوان)',
                    r'(nomor|number|numéro|nummer|番号|번호|号码|رقم)'
                ],
                'weight': 2
            }
        }
        
        # Enhanced grounding patterns
        self.grounding_patterns = {
            'high_priority': {
                'patterns': [
                    # Current events and news
                    r'(terbaru|latest|recent|breaking|aktual)',
                    r'(hari ini|today|sekarang|now|saat ini)',
                    r'(berita|news|kejadian|events|peristiwa)',
                    r'(2024|2025|tahun ini|this year)',
                    r'(kemarin|yesterday|minggu ini|this week)',
                    
                    # Real-time queries
                    r'(siapa yang|who is|who are|siapa sekarang)',
                    r'(apa yang terjadi|what happened|what\'s happening)',
                    r'(dimana|where is|where are|lokasi)',
                    r'(kapan|when did|when will|jadwal)',
                    
                    # Factual information
                    r'(berapa|how much|how many|price|harga)',
                    r'(statistik|data|facts|fakta|informasi)',
                    r'(populasi|population|jumlah penduduk)',
                    r'(alamat|address|location|tempat)',
                    
                    # Specific domains
                    r'(weather|cuaca|temperature|suhu)',
                    r'(stock|saham|cryptocurrency|crypto)',
                    r'(election|pemilu|politik|government)',
                    r'(sports|olahraga|match|pertandingan)',
                    r'(technology|teknologi|gadget|software)',
                    r'(health|kesehatan|medical|medis)',
                    r'(ekonomi|economy|inflation|inflasi)'
                ],
                'weight': 3
            },
            'medium_priority': {
                'patterns': [
                    # General factual queries
                    r'(apa itu|what is|qu\'est-ce que|was ist)',
                    r'(siapa|who|qui|wer)',
                    r'(mengapa|why|pourquoi|warum)',
                    r'(bagaimana|how|comment|wie)',
                    
                    # Comparison and analysis
                    r'(bandingkan|compare|comparison|perbandingan)',
                    r'(difference|perbedaan|berbeda|distinct)',
                    r'(lebih baik|better|best|terbaik)',
                    r'(vs|versus|dibanding|compared to)',
                    
                    # Academic and research
                    r'(penelitian|research|study|studi)',
                    r'(university|universitas|college|kampus)',
                    r'(buku|book|artikel|article|paper)',
                    r'(definisi|definition|meaning|arti)',
                    
                    # Business and companies
                    r'(company|perusahaan|corporation|bisnis)',
                    r'(CEO|founder|pendiri|owner|pemilik)',
                    r'(product|produk|service|layanan)',
                    r'(market|pasar|industry|industri)'
                ],
                'weight': 2
            },
            'low_priority': {
                'patterns': [
                    # General knowledge
                    r'(sejarah|history|historical|historique)',
                    r'(budaya|culture|tradition|tradisi)',
                    r'(bahasa|language|linguistic|linguistik)',
                    r'(negara|country|nation|bangsa)',
                    
                    # Educational content
                    r'(pelajaran|lesson|tutorial|guide)',
                    r'(explain|jelaskan|cara|method)',
                    r'(tips|advice|saran|recommendation)',
                    r'(example|contoh|sample|ilustrasi)'
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
            self.model_name = "gemini-2.5-flash"  # Set the actual model name
            self.text_model = genai.GenerativeModel(self.model_name)
            
            # Initialize vision model (same model for both text and vision)
            self.vision_model = self.text_model
            
            # Initialize grounding client and tools
            self.grounding_client = google_genai.Client(api_key=self.api_key)
            self.grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )
            self.grounding_config = types.GenerateContentConfig(
                tools=[self.grounding_tool]
            )
            
            logger.info(f"AI models initialized successfully with model: {self.model_name}")
            logger.info("Google Search grounding enabled")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.text_model = None
            self.vision_model = None
            self.grounding_client = None
    
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
            
            # Check if grounding should be used
            use_grounding = self._should_use_grounding(intent_analysis, message)
            
            if use_grounding and self.grounding_client:
                return await self._generate_grounded_response(message, intent_analysis, user_context, conversation_history)
            else:
                return await self._generate_standard_response(message, intent_analysis, user_context, conversation_history)
            
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            return None
    
    def _should_use_grounding(self, intent_analysis: Dict, message: str) -> bool:
        """Enhanced logic to determine if Google Search grounding should be used."""
        # Always use grounding for current events
        if intent_analysis['primary_intent'] == 'current_events':
            return True
        
        # Always use grounding for factual queries
        if intent_analysis['primary_intent'] == 'factual_query':
            return True
        
        message_lower = message.lower()
        grounding_score = 0
        
        # Calculate grounding score based on patterns
        for priority, data in self.grounding_patterns.items():
            for pattern in data['patterns']:
                matches = len(re.findall(pattern, message_lower, re.IGNORECASE))
                grounding_score += matches * data['weight']
        
        # Additional scoring factors
        
        # Question words that often need real-time data
        question_indicators = [
            r'\b(apa|what|siapa|who|dimana|where|kapan|when|berapa|how much|how many)\b',
            r'\b(bagaimana|how|mengapa|why|apakah|is|are)\b'
        ]
        for pattern in question_indicators:
            if re.search(pattern, message_lower):
                grounding_score += 1
        
        # Time-sensitive keywords
        time_keywords = [
            r'\b(2024|2025|tahun ini|this year|bulan ini|this month)\b',
            r'\b(tadi|just|baru saja|recently|lately)\b',
            r'\b(akan|will|future|masa depan|nanti)\b'
        ]
        for pattern in time_keywords:
            if re.search(pattern, message_lower):
                grounding_score += 2
        
        # Factual information indicators
        factual_indicators = [
            r'\b(data|statistics|facts|informasi|detail|specification)\b',
            r'\b(official|resmi|accurate|akurat|valid)\b',
            r'\b(source|sumber|reference|referensi)\b'
        ]
        for pattern in factual_indicators:
            if re.search(pattern, message_lower):
                grounding_score += 1
        
        # Proper nouns (likely need current info)
        if re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', message):
            grounding_score += 1
        
        # Numbers and quantities (often factual)
        if re.search(r'\b\d+(?:[.,]\d+)*\b', message):
            grounding_score += 1
        
        # Technical or specific domains
        domain_keywords = [
            r'\b(API|software|hardware|programming|coding)\b',
            r'\b(medicine|medical|health|treatment|obat)\b',
            r'\b(legal|law|regulation|peraturan|hukum)\b',
            r'\b(finance|financial|investment|investasi)\b'
        ]
        for pattern in domain_keywords:
            if re.search(pattern, message_lower, re.IGNORECASE):
                grounding_score += 2
        
        # Uncertainty indicators (user might need verified info)
        uncertainty_indicators = [
            r'\b(correct|benar|accurate|akurat|sure|yakin)\b',
            r'\b(verify|verifikasi|confirm|konfirmasi)\b',
            r'\b(real|nyata|actual|sebenarnya)\b'
        ]
        for pattern in uncertainty_indicators:
            if re.search(pattern, message_lower):
                grounding_score += 1
        
        # Lower threshold for using grounding (more frequent)
        grounding_threshold = 2  # Reduced from higher threshold
        
        # Special cases that should always use grounding
        always_ground_patterns = [
            r'\b(price|harga|cost|biaya)\b.*\b(today|hari ini|now|sekarang)\b',
            r'\b(status|kondisi|condition)\b.*\b(current|terkini|latest)\b',
            r'\b(update|pembaruan|info terbaru)\b',
            r'\b(live|realtime|real-time)\b'
        ]
        
        for pattern in always_ground_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return True
        
        # Use grounding if score meets threshold
        use_grounding = grounding_score >= grounding_threshold
        
        # Log grounding decision for debugging
        logger.info(f"Grounding decision - Score: {grounding_score}, Threshold: {grounding_threshold}, Use: {use_grounding}")
        logger.info(f"Message: {message[:50]}...")
        
        return use_grounding
    
    async def _generate_grounded_response(self, message: str, intent_analysis: Dict, user_context: dict = None, conversation_history: list = None) -> Optional[str]:
        """Generate response using Google Search grounding with enhanced prompts."""
        try:
            style_prompt = self.get_response_prompt(intent_analysis, False)
            system_prompt = self._build_system_prompt(intent_analysis, style_prompt, user_context)
            conversation_context = self._build_conversation_context(conversation_history)
            
            # Enhanced grounding instruction
            grounding_instruction = """
IMPORTANT: Use Google Search to find the most current, accurate, and up-to-date information for this query.
- Prioritize recent information and real-time data
- Verify facts with multiple sources when possible
- Include specific details like dates, numbers, and proper nouns
- If information is time-sensitive, mention when it was last updated
"""
            
            grounded_prompt = f"{system_prompt}\n{grounding_instruction}\n{conversation_context}\n\nUser Message: {message}"
            
            response = self.grounding_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=grounded_prompt,
                config=self.grounding_config
            )
            
            generated_text = response.text.strip() if response and response.text else None
            
            # Add grounding indicator for debugging
            if generated_text:
                logger.info("Response generated with Google Search grounding")
            
            return self._post_process_response(generated_text, intent_analysis) if generated_text else None
            
        except Exception as e:
            logger.error(f"Grounded response generation error: {e}")
            # Fallback to standard response
            return await self._generate_standard_response(message, intent_analysis, user_context, conversation_history)
    
    async def _generate_standard_response(self, message: str, intent_analysis: Dict, user_context: dict = None, conversation_history: list = None) -> Optional[str]:
        """Generate standard response without grounding."""
        try:
            style_prompt = self.get_response_prompt(intent_analysis, False)
            system_prompt = self._build_system_prompt(intent_analysis, style_prompt, user_context)
            conversation_context = self._build_conversation_context(conversation_history)
            
            full_prompt = f"{system_prompt}{conversation_context}\n\nUser Message: {message}"
            response = self.text_model.generate_content(full_prompt)
            
            generated_text = response.text.strip() if response and response.text else None
            return self._post_process_response(generated_text, intent_analysis) if generated_text else None
            
        except Exception as e:
            logger.error(f"Standard response generation error: {e}")
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
    
    def is_grounding_available(self) -> bool:
        """Check if Google Search grounding is available."""
        return self.grounding_client is not None and self.grounding_tool is not None

# Global instance
ai_core = AICore()
