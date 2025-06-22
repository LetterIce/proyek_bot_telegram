from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from utils import admin_only, format_stats
from database import db

__description__ = "Bot statistics and analytics"
__version__ = "1.0.0"
__author__ = "@Yuand_aa"

@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display bot statistics."""
    stats = db.get_stats()
    formatted_stats = format_stats(stats)
    await update.message.reply_text(formatted_stats, parse_mode='Markdown')

@admin_only
async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display user-specific statistics."""
    if not context.args:
        await update.message.reply_text("Usage: /userstats <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        history = db.get_user_history(user_id, limit=5)
        
        if not history:
            await update.message.reply_text(f"No data found for user {user_id}")
            return
        
        text = f"📊 **Stats for User {user_id}**\n\n"
        text += f"Total messages: {len(history)}\n"
        text += f"Last 5 messages:\n\n"
        
        for msg in history:
            text += f"🕐 {msg['timestamp']}\n"
            text += f"👤 {msg['message_text'][:50]}...\n"
            text += f"🤖 {msg['response_text'][:50]}...\n\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    except ValueError:
        await update.message.reply_text("Invalid user ID")

def setup(application):
    """Setup plugin handlers."""
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("userstats", user_stats))
