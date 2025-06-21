import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get configuration from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else None

# Validate required configuration
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable is required")
