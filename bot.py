import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, ADMIN_ID, PLUGINS_ENABLED, LOG_LEVEL, LOG_FILE, GEMINI_ENABLED, USE_GEMINI_FOR_UNKNOWN
from database import db
from gemini_client import gemini_client
from utils import registered_only, admin_only, rate_limit, update_user_info, broadcast_message, format_user_info, split_message, is_admin, update_user_activity

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL),
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Add path for media files
MEDIA_DIR = os.path.join(os.path.dirname(__file__), 'media')
LOADING_GIF_PATH = os.path.join(MEDIA_DIR, 'loading.gif')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    update_user_info(user)
    
    welcome_text = (
        f"👋 Halo, {user.first_name}! Senang bertemu dengan Anda.\n\n"
        "Saya adalah bot AI yang siap menjadi teman diskusi Anda.\n"
        "Anda bisa bertanya apa saja, mulai dari hal ringan hingga topik yang kompleks.\n"
        "Mau coba? Tanyakan sesuatu pada saya!"
    )
    
    await update.message.reply_text(welcome_text)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /register command."""
    user_id = update.effective_user.id
    
    if db.is_registered(user_id):
        await update.message.reply_text("✅ Anda sudah terdaftar!")
        return
    
    if db.register_user(user_id):
        await update.message.reply_text("🎉 Pendaftaran berhasil! Anda sekarang bisa menggunakan semua fitur bot.")
    else:
        await update.message.reply_text("❌ Gagal mendaftar. Silakan coba lagi.")

@rate_limit
@registered_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    update_user_activity(user_id)
    
    # Check for keyword response first
    response = db.get_keyword_response(text.lower())
    
    if response:
        await update.message.reply_text(response)
        db.log_message(user_id, text, response)
        db.increment_user_message_count(user_id)
        return
    
    # Handle Gemini AI response for all other messages
    if GEMINI_ENABLED and gemini_client.is_available():
        loading_message = None
        
        try:
            # Try to send loading GIF if it exists
            if os.path.exists(LOADING_GIF_PATH):
                with open(LOADING_GIF_PATH, 'rb') as gif_file:
                    loading_message = await update.message.reply_animation(
                        animation=gif_file,
                        caption="💭 Sedang berpikir..."
                    )
            else:
                loading_message = await update.message.reply_text("💭 Sedang memproses permintaan Anda...")
        except Exception as e:
            logger.warning(f"Failed to send loading indicator: {e}")
            loading_message = await update.message.reply_text("🤔 Sedang berpikir...")
        
        # Check if this is user's first interaction
        message_count = db.get_user_message_count(user_id)
        is_first_interaction = message_count == 0
        
        user_info = {
            'first_name': update.effective_user.first_name,
            'is_admin': is_admin(user_id),
            'is_first_interaction': is_first_interaction
        }
        
        gemini_response = await gemini_client.generate_response(text, user_info)
        
        # Delete loading message
        if loading_message:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, 
                    message_id=loading_message.message_id
                )
            except Exception as e:
                logger.warning(f"Failed to delete loading message: {e}")
        
        if gemini_response:
            if len(gemini_response) > 10000:
                gemini_response = gemini_response[:9970] + "..."
            
            # Send response without robot emoji prefix
            await update.message.reply_text(gemini_response)
            db.log_message(user_id, text, gemini_response, 'gemini')
        else:
            # Only show error if Gemini fails to respond
            error_response = "Maaf, terjadi kesalahan saat memproses permintaan Anda. Silakan coba lagi."
            await update.message.reply_text(error_response)
            db.log_message(user_id, text, error_response)
        
        # Increment message count after successful interaction
        db.increment_user_message_count(user_id)
    else:
        # Show message if Gemini is disabled or unavailable
        offline_response = "Fitur AI sedang tidak tersedia. Silakan coba lagi nanti."
        await update.message.reply_text(offline_response)
        db.log_message(user_id, text, offline_response)
        db.increment_user_message_count(user_id)

@registered_only
async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands (messages starting with /)."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    update_user_activity(user_id)
    
    # Response specifically for invalid commands
    command_response = "Maaf, saya tidak mengerti perintah itu. Ketik /help untuk bantuan."
    await update.message.reply_text(command_response)
    db.log_message(user_id, text, command_response)

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
        await update.message.reply_text("❌ Format: `/addkeyword <keyword> | <response>`\n\nContoh:\n`/addkeyword halo | Halo! Selamat datang di bot ini!`", parse_mode='Markdown')
        return
    
    try:
        full_text = ' '.join(context.args)
        
        if '|' not in full_text:
            await update.message.reply_text("❌ Format salah! Gunakan:\n`/addkeyword <keyword> | <response>`\n\nContoh:\n`/addkeyword halo | Halo! Selamat datang!`", parse_mode='Markdown')
            return
        
        parts = full_text.split('|', 1)
        keyword = parts[0].strip().lower()
        response = parts[1].strip()
        
        if not keyword or not response:
            await update.message.reply_text("❌ Keyword dan response tidak boleh kosong!")
            return
        
        if len(keyword) > 100:
            await update.message.reply_text("❌ Keyword terlalu panjang! Maksimal 100 karakter.")
            return
        
        if len(response) > 2000:
            await update.message.reply_text("❌ Response terlalu panjang! Maksimal 2000 karakter.")
            return
        
        logger.info(f"Admin {update.effective_user.id} attempting to add keyword: '{keyword}'")
        
        if db.add_keyword(keyword, response, update.effective_user.id):
            await update.message.reply_text(f"✅ Keyword `{keyword}` berhasil ditambahkan!", parse_mode='Markdown')
            logger.info(f"Keyword '{keyword}' added successfully")
        else:
            await update.message.reply_text(f"❌ Keyword `{keyword}` sudah ada! Gunakan keyword yang berbeda.", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in add_keyword: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat menambahkan keyword. Silakan coba lagi.")

@admin_only
async def delete_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete keyword."""
    if not context.args:
        await update.message.reply_text("❌ Format: `/delkeyword <keyword>`\n\nContoh:\n`/delkeyword halo`", parse_mode='Markdown')
        return
    
    try:
        keyword = ' '.join(context.args).strip().lower()
        
        if not keyword:
            await update.message.reply_text("❌ Keyword tidak boleh kosong!")
            return
        
        logger.info(f"Admin {update.effective_user.id} attempting to delete keyword: '{keyword}'")
        
        if db.delete_keyword(keyword):
            await update.message.reply_text(f"✅ Keyword `{keyword}` berhasil dihapus!", parse_mode='Markdown')
            logger.info(f"Keyword '{keyword}' deleted successfully")
        else:
            await update.message.reply_text(f"❌ Keyword `{keyword}` tidak ditemukan!", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in delete_keyword: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat menghapus keyword. Silakan coba lagi.")

@admin_only
async def list_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all keywords."""
    try:
        logger.info(f"Admin {update.effective_user.id} requesting keyword list")
        keywords = db.get_all_keywords()
        
        if not keywords:
            await update.message.reply_text("❌ Belum ada keyword yang tersedia.\n\nGunakan `/addkeyword <keyword> | <response>` untuk menambahkan keyword baru.", parse_mode='Markdown')
            return
        
        message = f"📝 **Daftar Keywords** ({len(keywords)} total):\n\n"
        
        for i, keyword_data in enumerate(keywords, 1):
            keyword = keyword_data.get('keyword', 'Unknown')
            response = keyword_data.get('response', 'No response')
            usage_count = keyword_data.get('usage_count', 0)
            created_at = keyword_data.get('created_at', 'Unknown')
            
            display_response = response[:80] + "..." if len(response) > 80 else response
            
            if created_at and created_at != 'Unknown':
                try:
                    date_part = created_at[:10]
                except:
                    date_part = 'Unknown'
            else:
                date_part = 'Unknown'
            
            entry = (
                f"{i}. **{keyword}**\n"
                f"   📝 Response: {display_response}\n"
                f"   📊 Used: {usage_count}x\n"
                f"   📅 Created: {date_part}\n\n"
            )
            message += entry
        
        chunks = split_message(message, max_length=4000)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode='Markdown')
            
        logger.info(f"Successfully sent keyword list with {len(keywords)} keywords")
        
    except Exception as e:
        logger.error(f"Error in list_keywords: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat mengambil daftar keyword. Silakan coba lagi.")

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

@admin_only
async def gemini_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check Gemini status."""
    status = "✅ Gemini 2.5 Pro: Online" if gemini_client.is_available() else "❌ Gemini 2.5 Pro: Offline"
    config_status = f"🔧 Gemini Enabled: {'Yes' if GEMINI_ENABLED else 'No'}\n"
    config_status += f"🎯 Auto Response: {'Yes' if USE_GEMINI_FOR_UNKNOWN else 'No'}"
    
    await update.message.reply_text(f"{status}\n{config_status}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    user_id = update.effective_user.id
    
    help_text = (
        "**Bot Help**\n\n"
        "**General Commands:**\n"
        "/start - Start the bot\n"
        "/register - Register as member\n"
        "/help - Show this help\n\n"
    )
    
    if is_admin(user_id):
        help_text += (
            "**Admin Commands:**\n"
            "/addkeyword `<keyword> | <response>` - Add keyword\n"
            "/delkeyword `<keyword>` - Delete keyword\n"
            "/listkeyword - List all keywords\n"
            "/listmembers - List all users\n"
            "/addadmin `<user_id>` - Add admin\n"
            "/broadcast `<message>` - Broadcast message\n"
            "/history [user_id] - View message history\n"
            "/stats - View bot statistics\n"
        )
        
        if GEMINI_ENABLED:
            help_text += "/geministatus - Check Gemini status\n"
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

@admin_only
async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View bot statistics."""
    try:
        users = db.get_all_users()
        registered_users = db.get_registered_users()
        
        stats_text = (
            f"📊 **Bot Statistics:**\n\n"
            f"👥 Total Users: {len(users)}\n"
            f"✅ Registered Users: {len(registered_users)}\n"
            f"🚀 Bot Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in view_stats: {e}")
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
                await update.message.reply_text("❌ Invalid user ID.")
                return
        else:
            history = db.get_global_history(10)
            title = "📝 Global Message History:\n\n"
        
        if not history:
            await update.message.reply_text("📭 No history found.")
            return
        
        message = title
        for i, record in enumerate(history, 1):
            timestamp = record.get('timestamp', 'Unknown time')
            user_id = record.get('user_id', 'Unknown user')
            message_text = record.get('message_text', 'No message')[:50]
            response_text = record.get('response_text', 'No response')[:50]
            
            entry = (
                f"{i}. 🕐 {timestamp}\n"
                f"   👤 User {user_id}: {message_text}...\n"
                f"   🤖 Bot: {response_text}...\n\n"
            )
            message += entry
        
        chunks = split_message(message, max_length=4000)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in view_history: {e}")
        await update.message.reply_text("❌ Error retrieving message history.")

def main():
    """Main function to run the bot."""
    # Create media directory if it doesn't exist
    os.makedirs(MEDIA_DIR, exist_ok=True)
    
    # Check if loading GIF exists
    if not os.path.exists(LOADING_GIF_PATH):
        logger.warning(f"Loading GIF not found at {LOADING_GIF_PATH}")
        logger.info("Bot will use text loading indicator instead")
    else:
        logger.info("Loading GIF found - will use animated loading indicator")
    
    db.set_admin(ADMIN_ID, True)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("addkeyword", add_keyword))
    application.add_handler(CommandHandler("delkeyword", delete_keyword))
    application.add_handler(CommandHandler("listkeyword", list_keywords))
    application.add_handler(CommandHandler("listmembers", list_members))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("history", view_history))
    application.add_handler(CommandHandler("stats", view_stats))
    
    if GEMINI_ENABLED:
        application.add_handler(CommandHandler("geministatus", gemini_status))
    
    # Load plugins if enabled
    if PLUGINS_ENABLED:
        try:
            from plugins import plugin_manager
            loaded_plugins = plugin_manager.load_plugins(application)
            if loaded_plugins:
                logger.info(f"Loaded {len(loaded_plugins)} plugins: {', '.join(loaded_plugins)}")
            else:
                logger.info("No plugins found or loaded")
        except ImportError:
            logger.warning("Plugin system not available - continuing without plugins")
        except Exception as e:
            logger.error(f"Error loading plugins: {e}")
    
    # Handle unknown commands (messages starting with / but not recognized)
    application.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
    
    # Handle regular text messages (not commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()