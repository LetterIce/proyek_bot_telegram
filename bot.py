import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, ADMIN_ID, PLUGINS_ENABLED, LOG_LEVEL, LOG_FILE, GEMINI_ENABLED
from database import db
from ai_core import ai_core
from utils import registered_only, admin_only, rate_limit, update_user_info, broadcast_message, format_user_info, split_message, is_admin, update_user_activity
from image_utils import download_image, validate_and_process_image, get_image_info, is_image_file
from system_info import format_system_stats

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

def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def escape_markdown(text: str) -> str:
    """Escape special characters for Markdown."""
    special_chars = ['_', '*', '[', ']', '(', ')', '`']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

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
    
    # Handle AI response
    if GEMINI_ENABLED and ai_core.is_available():
        loading_message = await send_loading_indicator(update, context)
        
        user_info = {
            'first_name': update.effective_user.first_name,
            'is_admin': is_admin(user_id),
            'is_first_interaction': db.get_user_message_count(user_id) == 0
        }
        
        conversation_history = db.get_conversation_context(user_id) if db.is_context_enabled(user_id) else []
        ai_response = await ai_core.generate_response(text, user_info, conversation_history)
        
        await delete_loading_message(loading_message, context, update.effective_chat.id)
        
        if ai_response:
            if len(ai_response) > 10000:
                ai_response = ai_response[:9970] + "..."
            
            await update.message.reply_text(ai_response)
            db.log_message(user_id, text, ai_response, 'ai')
            
            if db.is_context_enabled(user_id):
                db.add_conversation_message(user_id, text, ai_response)
        else:
            error_response = "Maaf, terjadi kesalahan saat memproses permintaan Anda. Silakan coba lagi."
            await update.message.reply_text(error_response)
            db.log_message(user_id, text, error_response)
        
        db.increment_user_message_count(user_id)
    else:
        offline_response = "Fitur AI sedang tidak tersedia. Silakan coba lagi nanti."
        await update.message.reply_text(offline_response)
        db.log_message(user_id, text, offline_response)
        db.increment_user_message_count(user_id)

async def send_loading_indicator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send loading indicator (GIF or text)."""
    if os.path.exists(LOADING_GIF_PATH):
        with open(LOADING_GIF_PATH, 'rb') as gif_file:
            return await update.message.reply_animation(
                animation=gif_file,
                caption="💭 Sedang berpikir..."
            )
    else:
        return await update.message.reply_text("💭 Sedang memproses permintaan Anda...")

async def delete_loading_message(loading_message, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Delete loading message."""
    if loading_message:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        except Exception as e:
            logger.warning(f"Failed to delete loading message: {e}")

@rate_limit
@registered_only
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image messages."""
    user_id = update.effective_user.id
    update_user_activity(user_id)
    
    logger.info(f"Processing image from user {user_id}")
    
    # Get image and caption
    file_id, file_name = get_image_file_info(update.message)
    if not file_id:
        return
    
    caption = update.message.caption or ""
    
    # Check if AI Vision is available
    if not (GEMINI_ENABLED and ai_core.is_vision_available()):
        offline_response = "Maaf, fitur analisis gambar sedang tidak tersedia. 📷❌"
        await update.message.reply_text(offline_response)
        file_info = {'type': 'image', 'name': file_name}
        db.log_message(user_id, caption or "[Gambar tanpa caption]", offline_response, 'image', file_info)
        return
    
    # Send loading indicator
    if os.path.exists(LOADING_GIF_PATH):
        with open(LOADING_GIF_PATH, 'rb') as gif_file:
            loading_message = await update.message.reply_animation(
                animation=gif_file,
                caption="👁️ Sedang menganalisis gambar..."
            )
    else:
        loading_message = await update.message.reply_text("👁️ Sedang menganalisis gambar... 🔍")
    
    # Process image
    image_data = await download_image(context.bot, file_id)
    if not image_data:
        await handle_image_error(update, context, loading_message, "❌ Gagal mengunduh gambar. Pastikan gambar tidak terlalu besar dan coba lagi.", caption, file_name)
        return
    
    processed_image = validate_and_process_image(image_data)
    if not processed_image:
        await handle_image_error(update, context, loading_message, "❌ Format gambar tidak didukung atau gambar rusak. Coba dengan gambar format JPG, PNG, atau GIF.", caption, file_name)
        return
    
    # Analyze image
    user_info = {
        'first_name': update.effective_user.first_name,
        'is_admin': is_admin(user_id),
        'is_first_interaction': db.get_user_message_count(user_id) == 0
    }
    
    analysis = await ai_core.analyze_image(processed_image, caption, user_info)
    
    await delete_loading_message(loading_message, context, update.effective_chat.id)
    
    if analysis:
        if len(analysis) > 4000:
            analysis = analysis[:3970] + "..."
        
        await update.message.reply_text(analysis)
        
        image_info = get_image_info(processed_image)
        file_info = {
            'type': 'image',
            'name': file_name,
            'size': f"{image_info.get('width', 0)}x{image_info.get('height', 0)}"
        }
        
        message_text = caption or "[Gambar tanpa caption]"
        db.log_message(user_id, message_text, analysis, 'image', file_info)
        
        if db.is_context_enabled(user_id):
            db.add_conversation_message(user_id, message_text, analysis, file_info)
    else:
        error_response = "❌ Maaf, gagal menganalisis gambar. Coba lagi dalam beberapa saat."
        await update.message.reply_text(error_response)
        file_info = {'type': 'image', 'name': file_name}
        db.log_message(user_id, caption or "[Gambar tanpa caption]", error_response, 'image', file_info)
    
    db.increment_user_message_count(user_id)

def get_image_file_info(message):
    """Extract file ID and name from message."""
    if message.photo:
        photo = message.photo[-1]
        return photo.file_id, f"photo_{photo.file_unique_id}.jpg"
    elif message.document and is_image_file(message.document.file_name):
        photo = message.document
        return photo.file_id, photo.file_name or "image.jpg"
    return None, None

async def handle_image_error(update, context, loading_message, error_response, caption, file_name):
    """Handle image processing errors."""
    await update.message.reply_text(error_response)
    await delete_loading_message(loading_message, context, update.effective_chat.id)
    
    file_info = {'type': 'image', 'name': file_name}
    db.log_message(update.effective_user.id, caption or "[Gambar tanpa caption]", error_response, 'image', file_info)

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

@registered_only
async def clear_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear user's conversation history."""
    user_id = update.effective_user.id
    
    if db.clear_conversation_context(user_id):
        await update.message.reply_text(
            "🗑️ Riwayat percakapan Anda telah dihapus.\n"
            "Percakapan baru akan dimulai tanpa konteks sebelumnya."
        )
    else:
        await update.message.reply_text("❌ Gagal menghapus riwayat percakapan.")

@registered_only
async def conversation_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage conversation context settings."""
    user_id = update.effective_user.id
    
    if not context.args:
        # Show current settings
        enabled = db.is_context_enabled(user_id)
        limit = db.get_user_context_limit(user_id)
        context_history = db.get_conversation_context(user_id)
        
        status = "🟢 Aktif" if enabled else "🔴 Nonaktif"
        settings_text = (
            f"⚙️ **Pengaturan Percakapan:**\n\n"
            f"📝 Status Memori: {status}\n"
            f"📊 Batas Pesan: {limit} pesan\n"
            f"💬 Pesan Tersimpan: {len(context_history)} pesan\n\n"
            f"**Cara Penggunaan:**\n"
            f"`/conversation on` - Aktifkan memori\n"
            f"`/conversation off` - Nonaktifkan memori\n"
            f"`/conversation limit <angka>` - Atur batas pesan (1-50)\n"
            f"`/clearconversation` - Hapus riwayat percakapan"
        )
        
        await update.message.reply_text(settings_text, parse_mode='Markdown')
        return
    
    command = context.args[0].lower()
    
    if command == "on":
        db.set_user_context_settings(user_id, enabled=True)
        await update.message.reply_text("✅ Memori percakapan diaktifkan! Bot akan mengingat percakapan sebelumnya.")
    
    elif command == "off":
        db.set_user_context_settings(user_id, enabled=False)
        await update.message.reply_text("❌ Memori percakapan dinonaktifkan. Bot tidak akan mengingat percakapan sebelumnya.")
    
    elif command == "limit":
        if len(context.args) < 2:
            await update.message.reply_text("❌ Format: `/conversation limit <angka>`\nContoh: `/conversation limit 15`", parse_mode='Markdown')
            return
        
        try:
            new_limit = int(context.args[1])
            if new_limit < 1 or new_limit > 50:
                await update.message.reply_text("❌ Batas pesan harus antara 1-50.")
                return
            
            current_enabled = db.is_context_enabled(user_id)
            db.set_user_context_settings(user_id, enabled=current_enabled, max_messages=new_limit)
            await update.message.reply_text(f"✅ Batas pesan percakapan diatur ke {new_limit} pesan.")
        
        except ValueError:
            await update.message.reply_text("❌ Angka tidak valid.")
    
    else:
        await update.message.reply_text(
            "❌ Perintah tidak dikenal.\n\n"
            "Gunakan: `on`, `off`, atau `limit <angka>`",
            parse_mode='Markdown'
        )

@registered_only
async def show_conversation_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show conversation history for the user."""
    user_id = update.effective_user.id
    
    try:
        # Use the correct method that exists in the database
        conversations = db.get_conversation_context(user_id)
        
        if not conversations:
            await update.message.reply_text("📭 Belum ada riwayat percakapan.")
            return
        
        # Build response without complex markdown formatting
        response_lines = ["📚 Riwayat Percakapan:\n"]
        
        # Take only the last 10 conversations for display
        recent_conversations = conversations[-10:] if len(conversations) > 10 else conversations
        
        for i, conv in enumerate(recent_conversations, 1):
            # Handle different conversation formats
            if isinstance(conv, dict):
                # Use the correct field names from the database
                user_msg = conv.get('message_text', 'Pesan tidak diketahui')
                bot_msg = conv.get('response_text', 'Tidak ada respons')
                timestamp = conv.get('timestamp', '')
            else:
                # Handle if conv is a tuple or other format
                user_msg = str(conv)[:100] if conv else 'Pesan tidak diketahui'
                bot_msg = 'Respons tidak tersedia'
                timestamp = ''
            
            # Truncate long messages
            if len(user_msg) > 100:
                user_msg = user_msg[:97] + "..."
            if len(bot_msg) > 150:
                bot_msg = bot_msg[:147] + "..."
            
            # Clean text to avoid markdown issues
            user_msg = user_msg.replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '')
            bot_msg = bot_msg.replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '')
            
            timestamp_str = ""
            if timestamp:
                try:
                    if isinstance(timestamp, str):
                        # Parse ISO format timestamp and format it nicely
                        from datetime import datetime
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        timestamp_str = f" ({dt.strftime('%d/%m %H:%M')})"
                    else:
                        timestamp_str = f" ({timestamp.strftime('%d/%m %H:%M')})"
                except:
                    timestamp_str = ""
            
            response_lines.append(f"{i}.{timestamp_str}")
            response_lines.append(f"👤 {user_msg}")
            response_lines.append(f"🤖 {bot_msg}")
            response_lines.append("")  # Empty line for spacing
        
        # Join all lines
        full_response = "\n".join(response_lines)
        
        # Split into chunks if too long
        chunks = []
        if len(full_response) > 4000:
            lines = response_lines
            current_chunk = []
            current_length = 0
            
            for line in lines:
                line_length = len(line) + 1
                if current_length + line_length > 4000 and current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [line]
                    current_length = line_length
                else:
                    current_chunk.append(line)
                    current_length += line_length
            
            if current_chunk:
                chunks.append("\n".join(current_chunk))
        else:
            chunks = [full_response]
        
        # Send chunks as plain text to avoid markdown issues
        for i, chunk in enumerate(chunks):
            if i == 0:
                await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(f"📚 Riwayat Percakapan (lanjutan):\n\n{chunk}")
        
        # Add navigation hint
        await update.message.reply_text(
            "💡 Tips:\n"
            "• /clearconversation - Hapus riwayat\n"
            "• /conversation - Pengaturan percakapan"
        )
        
    except Exception as e:
        logger.error(f"Error showing conversation history: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat mengambil riwayat percakapan.")

@admin_only
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new admin."""
    if not context.args:
        await update.message.reply_text("Format: /addadmin <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        db.set_admin(target_user_id, True)
        await update.message.reply_text(f"✅ Pengguna {target_user_id} sekarang adalah admin.")
    except ValueError:
        await update.message.reply_text("❌ ID pengguna harus berupa angka.")

@admin_only
async def add_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new keyword."""
    if not context.args:
        await update.message.reply_text("❌ Format: `/addkeyword <kata_kunci> | <respon>`\n\nContoh:\n`/addkeyword halo | Halo! Selamat datang di bot ini!`", parse_mode='Markdown')
        return
    
    try:
        full_text = ' '.join(context.args)
        
        if '|' not in full_text:
            await update.message.reply_text("❌ Format salah! Gunakan:\n`/addkeyword <kata_kunci> | <respon>`\n\nContoh:\n`/addkeyword halo | Halo! Selamat datang!`", parse_mode='Markdown')
            return
        
        parts = full_text.split('|', 1)
        keyword = parts[0].strip().lower()
        response = parts[1].strip()
        
        if not keyword or not response:
            await update.message.reply_text("❌ Kata kunci dan respon tidak boleh kosong!")
            return
        
        if len(keyword) > 100:
            await update.message.reply_text("❌ Kata kunci terlalu panjang! Maksimal 100 karakter.")
            return
        
        if len(response) > 2000:
            await update.message.reply_text("❌ Respon terlalu panjang! Maksimal 2000 karakter.")
            return
        
        logger.info(f"Admin {update.effective_user.id} attempting to add keyword: '{keyword}'")
        
        if db.add_keyword(keyword, response, update.effective_user.id):
            await update.message.reply_text(f"✅ Kata kunci `{keyword}` berhasil ditambahkan!", parse_mode='Markdown')
            logger.info(f"Kata kunci '{keyword}' berhasil ditambahkan")
        else:
            await update.message.reply_text(f"❌ Kata kunci `{keyword}` sudah ada! Gunakan kata kunci yang berbeda.", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in add_keyword: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat menambahkan kata kunci. Silakan coba lagi.")

@admin_only
async def delete_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete keyword."""
    if not context.args:
        await update.message.reply_text("❌ Format: `/delkeyword <kata_kunci>`\n\nContoh:\n`/delkeyword halo`", parse_mode='Markdown')
        return
    
    try:
        keyword = ' '.join(context.args).strip().lower()
        
        if not keyword:
            await update.message.reply_text("❌ Kata kunci tidak boleh kosong!")
            return
        
        logger.info(f"Admin {update.effective_user.id} attempting to delete keyword: '{keyword}'")
        
        if db.delete_keyword(keyword):
            await update.message.reply_text(f"✅ Kata kunci `{keyword}` berhasil dihapus!", parse_mode='Markdown')
            logger.info(f"Kata kunci '{keyword}' berhasil dihapus")
        else:
            await update.message.reply_text(f"❌ Kata kunci `{keyword}` tidak ditemukan!", parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in delete_keyword: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat menghapus kata kunci. Silakan coba lagi.")

@admin_only
async def list_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all keywords."""
    try:
        logger.info(f"Admin {update.effective_user.id} requesting keyword list")
        keywords = db.get_all_keywords()
        
        if not keywords:
            await update.message.reply_text("❌ Belum ada kata kunci yang tersedia.\n\nGunakan `/addkeyword <kata_kunci> | <respon>` untuk menambahkan kata kunci baru.", parse_mode='Markdown')
            return
        
        message = f"📝 **Daftar Kata Kunci** ({len(keywords)} total):\n\n"
        
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
                f"   📝 Respon: {display_response}\n"
                f"   📊 Digunakan: {usage_count}x\n"
                f"   📅 Dibuat: {date_part}\n\n"
            )
            message += entry
        
        chunks = split_message(message, max_length=4000)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode='Markdown')
            
        logger.info(f"Successfully sent keyword list with {len(keywords)} keywords")
        
    except Exception as e:
        logger.error(f"Error in list_keywords: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat mengambil daftar kata kunci. Silakan coba lagi.")

@admin_only
async def list_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all members."""
    users = db.get_all_users()
    
    if not users:
        await update.message.reply_text("Belum ada pengguna.")
        return
    
    message = "👥 **Daftar Pengguna:**\n\n"
    for user in users:
        message += format_user_info(user) + "\n"
    
    chunks = split_message(message)
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode='Markdown')

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all registered users."""
    if not context.args:
        await update.message.reply_text("Format: /broadcast <pesan>")
        return
    
    message_to_send = ' '.join(context.args)
    users = db.get_registered_users()
    
    if not users:
        await update.message.reply_text("❌ Tidak ada pengguna terdaftar.")
        return
    
    await update.message.reply_text(f"📡 Memulai siaran ke {len(users)} pengguna...")
    
    results = await broadcast_message(context, message_to_send)
    
    report = (
        f"📊 **Hasil Siaran:**\n"
        f"✅ Berhasil: {results['success']}\n"
        f"❌ Gagal: {results['failed']}\n"
    )
    
    await update.message.reply_text(report, parse_mode='Markdown')

@admin_only
async def ai_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check AI status."""
    status = "✅ AI Core: Aktif" if ai_core.is_available() else "❌ AI Core: Nonaktif"
    config_status = f"🔧 AI Diaktifkan: {'Ya' if GEMINI_ENABLED else 'Tidak'}"
    
    # Get AI model information
    model_info = ""
    if ai_core.is_available():
        try:
            # Get model name from ai_core
            model_name = getattr(ai_core, 'model_name', 'Tidak diketahui')
            
            model_info = (
                f"🤖 Model AI: {model_name}\n"
            )
        except Exception as e:
            model_info = "🤖 Model AI: Gagal mendapatkan informasi model"
    else:
        model_info = "🤖 Model AI: Tidak tersedia"
    
    full_status = f"{status}\n{config_status}\n{model_info}"
    await update.message.reply_text(full_status)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    user_id = update.effective_user.id
    
    help_text = (
        "**Fitur Bot:**\n"
        "💬 Chat dengan AI - Kirim pesan teks apa saja\n"
        "📷 Analisis Gambar - Kirim foto dengan atau tanpa keterangan\n"
        "🗂️ Gambar Dokumen - Kirim gambar sebagai dokumen\n\n"
        "**Perintah Umum:**\n"
        "/start - Memulai bot\n"
        "/register - Daftar sebagai anggota\n"
        "/help - Tampilkan bantuan ini\n\n"
        "**Perintah Percakapan:**\n"
        "/conversation - Kelola pengaturan memori percakapan\n"
        "/clearconversation - Hapus riwayat percakapan\n"
        "/myhistory - Lihat riwayat percakapan Anda\n\n"
    )
    
    if is_admin(user_id):
        help_text += (
            "**Perintah Admin:**\n"
            "/addkeyword `<kata_kunci> | <respon>` - Tambah kata kunci\n"
            "/delkeyword `<kata_kunci>` - Hapus kata kunci\n"
            "/listkeyword - Lihat semua kata kunci\n"
            "/listmembers - Lihat semua pengguna\n"
            "/addadmin `<user_id>` - Tambah admin\n"
            "/broadcast `<pesan>` - Siaran pesan\n"
            "/history [user_id] - Lihat riwayat pesan\n"
            "/stats - Lihat statistik bot\n"
        )
        
        if GEMINI_ENABLED:
            help_text += "/aistatus - Cek status AI\n"
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

@admin_only
async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View bot statistics."""
    try:
        users = db.get_all_users()
        registered_users = db.get_registered_users()
        
        # Bot Statistics
        bot_stats = (
            f"📊 **Statistik Bot:**\n\n"
            f"👥 Total Pengguna: {len(users)}\n"
            f"✅ Pengguna Terdaftar: {len(registered_users)}\n"
            f"🚀 Bot Dimulai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        
        # Get system information
        system_stats = format_system_stats()
        
        # Combine both statistics
        full_stats = bot_stats + system_stats
        
        # Split message if too long
        chunks = split_message(full_stats, max_length=4000)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in view_stats: {e}")
        await update.message.reply_text("❌ Kesalahan saat mengambil statistik.")

@admin_only
async def view_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View message history (admin only - can view global or specific user)."""
    try:
        if context.args:
            try:
                target_user_id = int(context.args[0])
                history = db.get_user_history(target_user_id, 10)  # Increased limit
                if not history:
                    await update.message.reply_text(f"📭 Tidak ada riwayat untuk Pengguna {target_user_id}.")
                    return
                title = f"📝 Riwayat Pesan Pengguna {target_user_id} ({len(history)} pesan):\n\n"
            except ValueError:
                await update.message.reply_text("❌ ID pengguna tidak valid. Gunakan: /history <user_id> atau /history untuk riwayat global.")
                return
        else:
            history = db.get_global_history(10)  # Increased limit for global history
            if not history:
                await update.message.reply_text("📭 Tidak ada riwayat global.")
                return
            title = f"📝 Riwayat Pesan Global ({len(history)} pesan terbaru):\n\n"
        
        message = title
        for i, record in enumerate(reversed(history), 1):  # Show oldest first
            timestamp = record.get('timestamp', 'Waktu tidak diketahui')
            try:
                if timestamp and timestamp != 'Waktu tidak diketahui':
                    if isinstance(timestamp, str):
                        # Handle ISO format timestamp
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            date_part = dt.strftime('%d/%m %H:%M')
                        except:
                            date_part = timestamp[:16] if len(timestamp) >= 16 else timestamp
                    else:
                        date_part = timestamp.strftime('%d/%m %H:%M')
                else:
                    date_part = 'Tidak diketahui'
            except:
                date_part = 'Tidak diketahui'
            
            user_id_display = record.get('user_id', 'Pengguna tidak diketahui')
            message_text = record.get('message_text', 'Tidak ada pesan')
            response_text = record.get('response_text', 'Tidak ada respon')
            msg_type = record.get('message_type', 'text')
            
            # Clean and truncate text to avoid markdown parsing issues
            if len(message_text) > 80:
                message_text = message_text[:77] + "..."
            if len(response_text) > 80:
                response_text = response_text[:77] + "..."
            
            # Remove potentially problematic characters
            message_text = message_text.replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '').replace('(', '').replace(')', '')
            response_text = response_text.replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '').replace('(', '').replace(')', '')
            
            # Add type indicator
            type_indicator = ""
            if msg_type == 'image':
                type_indicator = "📷 "
            elif msg_type == 'ai':
                type_indicator = "🤖 "
            elif msg_type == 'normal':
                type_indicator = "💬 "
            
            entry = (
                f"{i}. 🕐 {date_part}\n"
                f"   👤 ID{user_id_display}: {type_indicator}{message_text}\n"
                f"   🤖 Bot: {response_text}\n\n"
            )
            message += entry
        
        # Send as plain text to avoid markdown parsing errors
        chunks = split_message(message, max_length=4000)
        for i, chunk in enumerate(chunks):
            if i == 0:
                await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(f"📝 Riwayat (lanjutan {i+1}):\n\n{chunk}")
            
    except Exception as e:
        logger.error(f"Error in view_history: {e}")
        await update.message.reply_text("❌ Kesalahan saat mengambil riwayat pesan.")

def main():
    """Main function to run the bot."""
    # Create media directory if it doesn't exist
    os.makedirs(MEDIA_DIR, exist_ok=True)
    
    # Check if loading GIF exists
    if not os.path.exists(LOADING_GIF_PATH):
        logger.warning(f"Loading GIF not found at {LOADING_GIF_PATH}")
        logger.info("Bot akan menggunakan indikator teks sebagai pengganti")
    else:
        logger.info("Loading GIF ditemukan - akan menggunakan indikator animasi")
    
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
    application.add_handler(CommandHandler("conversation", conversation_settings))
    application.add_handler(CommandHandler("clearconversation", clear_conversation))
    application.add_handler(CommandHandler("myhistory", show_conversation_history))
    
    if GEMINI_ENABLED:
        application.add_handler(CommandHandler("aistatus", ai_status))
    
    # Load plugins if enabled
    if PLUGINS_ENABLED:
        try:
            from plugins import plugin_manager
            loaded_plugins = plugin_manager.load_plugins(application)
            if loaded_plugins:
                logger.info(f"Loaded {len(loaded_plugins)} plugins: {', '.join(loaded_plugins)}")
            else:
                logger.info("Tidak ada plugin yang ditemukan atau dimuat")
        except ImportError:
            logger.warning("Sistem plugin tidak tersedia - melanjutkan tanpa plugin")
        except Exception as e:
            logger.error(f"Kesalahan saat memuat plugin: {e}")
    
    # Handle images (photos and image documents)
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_image))
    
    # Handle unknown commands (messages starting with / but not recognized)
    application.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
    
    # Handle regular text messages (not commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot berhasil dimulai!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()