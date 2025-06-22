import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable is required")

# Gemini Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_ENABLED = os.getenv('GEMINI_ENABLED', 'True').lower() == 'true'

# Database Configuration
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bot_database.db')

# Bot Settings
BOT_NAME = os.getenv("BOT_NAME", "Bot sangar")
BOT_VERSION = "2.0.0"
MAX_MESSAGE_LENGTH = 4096
BROADCAST_DELAY = 0.5

# Plugin Settings
PLUGINS_ENABLED = os.getenv('PLUGINS_ENABLED', 'False').lower() == 'true'
PLUGIN_DIR = "plugins"

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "bot.log"

# Rate Limiting
RATE_LIMIT_MESSAGES = 1000
RATE_LIMIT_WINDOW = 10

# Feature Flags
ENABLE_STATS = True
ENABLE_BACKUP = True
ENABLE_INLINE_QUERIES = True
ENABLE_CALLBACK_QUERIES = True