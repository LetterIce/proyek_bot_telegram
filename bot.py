import sqlite3
import os
import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from telegram.error import Forbidden, BadRequest
from config import BOT_TOKEN, ADMIN_ID

# Setup logging untuk debugging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def setup_database():
    """Menghubungkan ke database SQLite dan membuat tabel jika belum ada."""
    
    # Path untuk database SQLite
    db_path = os.path.join(os.path.dirname(__file__), 'bot_database.db')
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    
    # SQL untuk membuat tabel (SQLite syntax)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_registered INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            response TEXT NOT NULL
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_text TEXT,
            response_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    conn.commit()
    return conn

# Fungsi untuk mencatat riwayat pesan
def log_message(user_id, message, response):
    cursor = db_conn.cursor()
    cursor.execute(
        "INSERT INTO message_history (user_id, message_text, response_text, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, message, response, datetime.now())
    )
    db_conn.commit()

# Decorator untuk membatasi akses hanya untuk member terdaftar
def registered_only(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        cursor = db_conn.cursor()
        cursor.execute("SELECT is_registered FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            return await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text("Anda belum terdaftar. Silakan ketik /register untuk mendaftar.")
    return wrapped

# Decorator untuk membatasi akses hanya untuk admin
def admin_only(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        cursor = db_conn.cursor()
        cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result and result[0]:
            return await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text("Perintah ini hanya untuk admin.")
    return wrapped

# Fungsi untuk perintah /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username
    
    cursor = db_conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    db_conn.commit()
    
    await update.message.reply_text(f"Halo {user.first_name}! Selamat datang di bot. Ketik /register untuk mendaftar.")

# Fungsi untuk perintah /register
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor = db_conn.cursor()
    cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
    db_conn.commit()
    await update.message.reply_text("Pendaftaran berhasil! Anda sekarang bisa menggunakan fitur bot.")

@registered_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.lower()
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT response FROM keywords WHERE keyword = ?", (text, ))
    result = cursor.fetchone()
    
    response_text = "Maaf, saya tidak mengerti perintah itu."
    if result:
        response_text = result[0]
        
    await update.message.reply_text(response_text)
    # Catat ke history
    log_message(user_id, text, response_text)

# Menambah admin baru
@admin_only
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Ambil user_id dari pesan, misal: /addadmin 12345678
        target_user_id = int(context.args[0])
        cursor = db_conn.cursor()
        cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (target_user_id,))
        db_conn.commit()
        await update.message.reply_text(f"User ID {target_user_id} sekarang adalah admin.")
    except (IndexError, ValueError):
        await update.message.reply_text("Gunakan format: /addadmin <user_id>")

# Mengelola keyword
@admin_only
async def add_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Format: /addkeyword halo | Hai juga!
        parts = ' '.join(context.args).split('|')
        keyword = parts[0].strip().lower()
        response = parts[1].strip()
        
        cursor = db_conn.cursor()
        cursor.execute("INSERT INTO keywords (keyword, response) VALUES (?, ?)", (keyword, response))
        db_conn.commit()
        await update.message.reply_text(f"Keyword '{keyword}' berhasil ditambahkan.")
    except Exception as e:
        await update.message.reply_text(f"Gagal menambahkan keyword. Format: /addkeyword <keyword> | <jawaban>. Error: {e}")

@admin_only
async def delete_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        keyword = ' '.join(context.args).strip().lower()
        cursor = db_conn.cursor()
        cursor.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
        db_conn.commit()
        if cursor.rowcount > 0:
            await update.message.reply_text(f"Keyword '{keyword}' berhasil dihapus.")
        else:
            await update.message.reply_text(f"Keyword '{keyword}' tidak ditemukan.")
    except IndexError:
        await update.message.reply_text("Gunakan format: /delkeyword <keyword>")

# Mengelola member
@admin_only
async def list_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db_conn.cursor()
    cursor.execute("SELECT user_id, username, is_registered, is_admin FROM users")
    members = cursor.fetchall()
    if not members:
        await update.message.reply_text("Belum ada member.")
        return
    
    message = "Daftar User:\n"
    for member in members:
        reg_status = "Terdaftar" if member[2] else "Belum"
        admin_status = " (Admin)" if member[3] else ""
        message += f"- ID: `{member[0]}`, User: @{member[1]}, Status: {reg_status}{admin_status}\n"
    await update.message.reply_text(message, parse_mode='Markdown')

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_to_send = ' '.join(context.args)
    if not message_to_send:
        await update.message.reply_text("Gunakan format: /broadcast <pesan>")
        return
        
    cursor = db_conn.cursor()
    # Pastikan hanya broadcast ke member yang terdaftar
    cursor.execute("SELECT user_id, username FROM users WHERE is_registered = 1")
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("Tidak ada member terdaftar untuk di-broadcast.")
        return
        
    success_count = 0
    fail_count = 0
    failed_users = []

    # Kirim pesan konfirmasi awal
    await update.message.reply_text(f"Memulai broadcast ke {len(users)} member...")

    for user in users:
        user_id = user[0]
        username = user[1]
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            success_count += 1
        except Forbidden:
            # Ini terjadi jika user memblokir bot
            logging.warning(f"Gagal mengirim ke {user_id} (@{username}): User memblokir bot.")
            failed_users.append(f"@{username} (diblokir)")
            fail_count += 1
        except BadRequest as e:
            # Ini terjadi jika chat tidak ditemukan (user belum pernah start bot) atau error lainnya
            logging.warning(f"Gagal mengirim ke {user_id} (@{username}): Chat tidak ditemukan atau error lain. Detail: {e}")
            failed_users.append(f"@{username} (chat tidak ditemukan)")
            fail_count += 1
        except Exception as e:
            # Menangkap error tak terduga lainnya
            logging.error(f"Gagal mengirim ke {user_id} (@{username}) karena error tak terduga: {e}")
            failed_users.append(f"@{username} (error lain)")
            fail_count += 1
            
    # Laporan akhir
    final_report = f"Broadcast selesai.\n\nBerhasil terkirim: {success_count} user\nGagal terkirim: {fail_count} user"
    if failed_users:
        final_report += "\n\nDaftar Gagal:\n- " + "\n- ".join(failed_users)

    await update.message.reply_text(final_report)
    log_message(update.effective_user.id, f"[BROADCAST] {message_to_send}", f"Berhasil: {success_count}, Gagal: {fail_count}")

async def help_command(update: Update, context: CallbackContext): # Tambahkan 'async'
    """Menampilkan pesan bantuan yang berbeda untuk user biasa dan admin.""" 
    user_id = update.effective_user.id
    cursor = db_conn.cursor()
    
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    is_admin = result and result[0]

    help_text = (
        "👤 *Perintah Umum:*\n"
        "/start - Memulai bot\n"
        "/register - Mendaftar sebagai member untuk menggunakan fitur\n"
        "/help - Menampilkan pesan bantuan ini\n\n"
    )

    if is_admin:
        admin_help_text = (
            "\n\n"
            "👑 *Perintah Khusus Admin:*\n"
            "/addkeyword `<keyword> | <jawaban>` - Menambah keyword & balasan baru.\n"
            "/delkeyword `<keyword>` - Menghapus keyword.\n"
            "/listmembers - Melihat daftar semua pengguna dan statusnya.\n"
            "/addadmin `<user_id>` - Menjadikan pengguna lain sebagai admin.\n"
            "/broadcast `<pesan>` - Mengirim pesan ke semua member terdaftar.\n"
            "/history [<user_id>] - Melihat riwayat pesan.\n"
        )
        help_text += admin_help_text
    
    # Tambahkan 'await' di depan pemanggilan fungsi API
    await update.message.reply_text(help_text, parse_mode='Markdown')

@admin_only
async def view_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan riwayat pesan untuk semua user atau user spesifik."""
    cursor = db_conn.cursor()
    
    try:
        # Mode 1: Menampilkan riwayat untuk user spesifik
        # Contoh: /history 123456789
        target_user_id = int(context.args[0])
        cursor.execute(
            "SELECT timestamp, message_text, response_text FROM message_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10",
            (target_user_id,)
        )
        records = cursor.fetchall()
        
        if not records:
            await update.message.reply_text(f"Tidak ada riwayat pesan ditemukan untuk User ID: `{target_user_id}`.", parse_mode='Markdown')
            return
            
        history_title = f"📝 *Riwayat 10 Pesan Terakhir untuk User ID:* `{target_user_id}`\n\n"
        
        response_message = history_title
        for timestamp, message, response in records:
            formatted_time = timestamp
            
            response_message += f"🗓️ *{formatted_time}*\n"
            response_message += f"  👤 *User:* `{message or 'N/A'}`\n"
            response_message += f"  🤖 *Bot:* `{response or 'N/A'}`\n\n"

    except (IndexError, ValueError):
        # Mode 2: Menampilkan 10 pesan terakhir dari semua user
        # Jika tidak ada argumen atau argumen bukan angka
        cursor.execute(
            "SELECT user_id, timestamp, message_text, response_text FROM message_history ORDER BY timestamp DESC LIMIT 10"
        )
        records = cursor.fetchall()

        if not records:
            await update.message.reply_text("Belum ada riwayat pesan sama sekali di database.")
            return

        history_title = "📝 *Riwayat 10 Pesan Terakhir (Semua User)*\n\n"
        
        response_message = history_title
        for user_id, timestamp, message, response in records:
            formatted_time = timestamp
            
            response_message += f"🗓️ *{formatted_time}* (User ID: `{user_id}`)\n"
            response_message += f"  👤 *User:* `{message or 'N/A'}`\n"
            response_message += f"  🤖 *Bot:* `{response or 'N/A'}`\n\n"

    # Kirim pesan hasil format
    await update.message.reply_text(response_message, parse_mode='Markdown')

def main():
    global db_conn
    db_conn = setup_database()
    
    # Set admin as admin in database if not already set
    cursor = db_conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, 1)", (ADMIN_ID,))
    cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (ADMIN_ID,))
    db_conn.commit()
    
    application = Application.builder().token(BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("history", view_history))
    
    # Admin Command Handlers
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("addkeyword", add_keyword))
    application.add_handler(CommandHandler("delkeyword", delete_keyword))
    application.add_handler(CommandHandler("listmembers", list_members))
    application.add_handler(CommandHandler("broadcast", broadcast))

    # Message Handler (harus terakhir)
    # Menangani semua pesan teks yang bukan perintah
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Mulai bot
    application.run_polling()
    logging.info("Bot started polling...")

if __name__ == '__main__':
    main()