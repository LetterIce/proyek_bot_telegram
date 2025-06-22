import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, ADMIN_ID, PLUGINS_ENABLED, LOG_LEVEL, LOG_FILE
from database import db
from utils import (
    registered_only, admin_only, rate_limit, update_user_info, 
    broadcast_message, format_user_info, split_message, is_admin
)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL),
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    update_user_info(user)
    
    welcome_text = (
        f"🤖 Selamat datang {user.first_name}!\n\n"
        "Saya adalah bot canggih dengan fitur-fitur menarik.\n"
        "Ketik /register untuk mendaftar dan menggunakan semua fitur.\n"
        "Ketik /help untuk melihat daftar perintah."
    )
    
    await update.message.reply_text(welcome_text)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /register command."""
    user_id = update.effective_user.id
    
    if db.is_registered(user_id):
        await update.message.reply_text("✅ Anda sudah terdaftar!")
        return
    
    success = db.register_user(user_id)
    if success:
        await update.message.reply_text("🎉 Pendaftaran berhasil! Anda sekarang bisa menggunakan semua fitur bot.")
        db.update_stat('total_registrations', str(len(db.get_registered_users())))
    else:
        await update.message.reply_text("❌ Gagal mendaftar. Silakan coba lagi.")

@rate_limit
@registered_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    original_text = text
    text_lower = text.lower()
    
    # Update user activity (this won't affect registration status)
    from utils import update_user_activity
    update_user_activity(user_id)
    
    # Log the incoming message
    logger.info(f"User {user_id} sent message: {text[:50]}...")
    
    # Get keyword response
    response = db.get_keyword_response(text_lower)
    
    if response:
        await update.message.reply_text(response)
        # Log successful message interaction
        log_success = db.log_message(user_id, original_text, response)
        logger.info(f"Keyword response logged: {log_success}")
    else:
        default_response = "🤔 Maaf, saya tidak mengerti perintah itu. Ketik /help untuk bantuan."
        await update.message.reply_text(default_response)
        # Log default response
        log_success = db.log_message(user_id, original_text, default_response)
        logger.info(f"Default response logged: {log_success}")

@admin_only
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new admin."""
    if not context.args:
        await update.message.reply_text("Usage: /addadmin <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        db.set_admin(target_user_id, True)
        await update.message.reply_text(f"✅ User {target_user_id} sekarang adalah admin.")
    except ValueError:
        await update.message.reply_text("❌ User ID harus berupa angka.")

@admin_only
async def add_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new keyword."""
    if not context.args:
        await update.message.reply_text("Usage: /addkeyword <keyword> | <response>")
        return
    
    try:
        keyword, response = ' '.join(context.args).split('|', 1)
        keyword, response = keyword.strip().lower(), response.strip()
        
        if db.add_keyword(keyword, response, update.effective_user.id):
            await update.message.reply_text(f"✅ Keyword '{keyword}' berhasil ditambahkan.")
        else:
            await update.message.reply_text(f"❌ Keyword '{keyword}' sudah ada.")
    except ValueError:
        await update.message.reply_text("❌ Format: /addkeyword <keyword> | <response>")

@admin_only
async def delete_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete keyword."""
    if not context.args:
        await update.message.reply_text("Usage: /delkeyword <keyword>")
        return
    
    keyword = ' '.join(context.args).strip().lower()
    success_msg = f"✅ Keyword '{keyword}' berhasil dihapus." if db.delete_keyword(keyword) else f"❌ Keyword '{keyword}' tidak ditemukan."
    await update.message.reply_text(success_msg)

@admin_only
async def list_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all members."""
    users = db.get_all_users()
    
    if not users:
        await update.message.reply_text("Belum ada user.")
        return
    
    message = "👥 **Daftar User:**\n\n"
    for user in users:
        message += format_user_info(user) + "\n"
    
    # Split long messages
    chunks = split_message(message)
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode='Markdown')

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all registered users."""
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message_to_send = ' '.join(context.args)
    users = db.get_registered_users()
    
    if not users:
        await update.message.reply_text("❌ Tidak ada user terdaftar.")
        return
    
    await update.message.reply_text(f"📡 Memulai broadcast ke {len(users)} user...")
    
    results = await broadcast_message(context, message_to_send)
    
    report = (
        f"📊 **Hasil Broadcast:**\n"
        f"✅ Berhasil: {results['success']}\n"
        f"❌ Gagal: {results['failed']}\n"
    )
    
    await update.message.reply_text(report, parse_mode='Markdown')
    
    # Log broadcast
    db.log_message(
        update.effective_user.id,
        f"[BROADCAST] {message_to_send}",
        f"Success: {results['success']}, Failed: {results['failed']}",
        'broadcast'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    user_id = update.effective_user.id
    
    help_text = (
        "🤖 **Bot Help**\n\n"
        "**General Commands:**\n"
        "/start - Start the bot\n"
        "/register - Register as member\n"
        "/help - Show this help\n\n"
    )
    
    if is_admin(user_id):
        admin_help = (
            "**Admin Commands:**\n"
            "/addkeyword `<keyword> | <response>` - Add keyword\n"
            "/delkeyword `<keyword>` - Delete keyword\n"
            "/listmembers - List all users\n"
            "/addadmin `<user_id>` - Add admin\n"
            "/broadcast `<message>` - Broadcast message\n"
            "/history [user_id] - View message history\n"
            "/stats - View bot statistics\n"
            "/debug - Debug message history\n"
        )
        help_text += admin_help
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

@admin_only
async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View bot statistics."""
    try:
        stats = db.get_all_stats()
        users = db.get_all_users()
        registered_users = db.get_registered_users()
        
        stats_text = (
            f"📊 **Bot Statistics:**\n\n"
            f"👥 Total Users: {len(users)}\n"
            f"✅ Registered Users: {len(registered_users)}\n"
            f"🔧 Total Registrations: {stats.get('total_registrations', '0')}\n"
            f"📝 Total Messages: {stats.get('total_messages', '0')}\n"
            f"🚀 Bot Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await update.message.reply_text("❌ Error retrieving statistics.")

@admin_only
async def view_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View message history."""
    try:
        if context.args:
            try:
                target_user_id = int(context.args[0])
                history = db.get_user_history(target_user_id, 10)
                title = f"📝 History for User {target_user_id}:\n\n"
            except ValueError:
                await update.message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")
                return
        else:
            history = db.get_global_history(10)
            title = "📝 Global Message History:\n\n"
        
        if not history:
            await update.message.reply_text("📭 No history found.")
            return
        
        message = title
        for i, record in enumerate(history, 1):
            # Safely get values with defaults
            timestamp = record.get('timestamp', 'Unknown time')
            user_id = record.get('user_id', 'Unknown user')
            message_text = record.get('message_text', 'No message')[:100]
            response_text = record.get('response_text', 'No response')[:100]
            
            # Clean up the message text for safe display
            message_text = message_text.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            response_text = response_text.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            
            entry = (
                f"{i}. 🕐 {timestamp}\n"
                f"   👤 User {user_id}: {message_text}\n"
                f"   🤖 Bot: {response_text}\n\n"
            )
            message += entry
        
        # Split and send message chunks
        chunks = split_message(message, max_length=4000)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        await update.message.reply_text("❌ Error retrieving message history.")

@admin_only
async def debug_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug command to check message history table."""
    try:
        # Check if message_history table exists and has data
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check table structure
            cursor.execute("PRAGMA table_info(message_history)")
            table_info = cursor.fetchall()
            
            # Count total records
            cursor.execute("SELECT COUNT(*) FROM message_history")
            total_records = cursor.fetchone()[0]
            
            # Get recent records with more details
            cursor.execute("""
                SELECT id, user_id, message_text, response_text, timestamp 
                FROM message_history 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            recent_records = cursor.fetchall()
            
            debug_text = f"🔍 **Debug History:**\n\n"
            debug_text += f"📊 Total records: {total_records}\n"
            debug_text += f"📋 Table columns: {len(table_info)}\n\n"
            
            if table_info:
                debug_text += "🏗️ **Table Structure:**\n"
                for col in table_info:
                    debug_text += f"• {col[1]} ({col[2]})\n"
                debug_text += "\n"
            
            if recent_records:
                debug_text += "📝 **Recent Records:**\n"
                for record in recent_records:
                    debug_text += f"• ID: {record[0]}\n"
                    debug_text += f"  User: {record[1]}\n"
                    debug_text += f"  Message: {record[2][:30]}...\n"
                    debug_text += f"  Response: {record[3][:30]}...\n"
                    debug_text += f"  Time: {record[4]}\n\n"
            else:
                debug_text += "❌ No records found in message_history table\n"
            
            # Also check if there are any users
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            debug_text += f"👥 Total users in database: {user_count}\n"
            
            await update.message.reply_text(debug_text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Debug history error: {e}")
        await update.message.reply_text(f"❌ Debug error: {str(e)}")

def main():
    """Main function to run the bot."""
    # Initialize admin in database
    db.set_admin(ADMIN_ID, True)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Load plugins if enabled
    if PLUGINS_ENABLED:
        try:
            from plugins import plugin_manager
            loaded_plugins = plugin_manager.load_plugins(application)
            logger.info(f"Loaded {len(loaded_plugins)} plugins: {', '.join(loaded_plugins)}")
        except Exception as e:
            logger.error(f"Failed to load plugins: {e}")
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("addkeyword", add_keyword))
    application.add_handler(CommandHandler("delkeyword", delete_keyword))
    application.add_handler(CommandHandler("listmembers", list_members))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("history", view_history))
    application.add_handler(CommandHandler("stats", view_stats))
    application.add_handler(CommandHandler("debug", debug_history))  # Add debug command
    
    # Add message handler (must be last)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()