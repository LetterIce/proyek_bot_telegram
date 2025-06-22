import os
from typing import List

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable is required")

# Database Configuration
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'bot_database.db')

# Additional Admins (besides main admin)
ADDITIONAL_ADMINS: List[int] = []

# Bot Settings
BOT_NAME = os.getenv("BOT_NAME", "Bot sangar")
BOT_VERSION = "2.0.0"
MAX_MESSAGE_LENGTH = 4096
BROADCAST_DELAY = 0.5  # seconds between broadcast messages

# Plugin Settings
PLUGINS_ENABLED = True
PLUGIN_DIR = "plugins"

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "bot.log"

# Rate Limiting
RATE_LIMIT_MESSAGES = 1000  # messages per minute per user
RATE_LIMIT_WINDOW = 10    # seconds

# Feature Flags
ENABLE_STATS = True
ENABLE_BACKUP = True
ENABLE_INLINE_QUERIES = True
ENABLE_CALLBACK_QUERIES = True
