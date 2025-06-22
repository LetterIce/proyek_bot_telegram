"""
Bot runner script with environment variable loading.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import and run the bot
try:
    from bot import main
    if __name__ == "__main__":
        main()
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Error starting bot: {e}")
    sys.exit(1)
