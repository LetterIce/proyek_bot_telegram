import asyncio
import logging
import functools
from datetime import datetime, timedelta
from typing import Callable
from telegram import Update, User
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest
from database import db
from config import RATE_LIMIT_MESSAGES, RATE_LIMIT_WINDOW, ADMIN_ID

logger = logging.getLogger(__name__)

def registered_only(func: Callable) -> Callable:
    """Decorator to restrict access to registered users only."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not db.is_registered(user_id):
            await update.message.reply_text("❌ Anda belum terdaftar. Silakan ketik /register untuk mendaftar.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def admin_only(func: Callable) -> Callable:
    """Decorator to restrict access to admins only."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("❌ Perintah ini hanya untuk admin.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def rate_limit(func: Callable) -> Callable:
    """Decorator to implement rate limiting."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if is_admin(user_id) or check_rate_limit(user_id):
            return await func(update, context, *args, **kwargs)
        
        await update.message.reply_text("⚠️ Anda mengirim pesan terlalu cepat. Silakan tunggu sebentar.")
    return wrapper

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == ADMIN_ID or db.is_admin(user_id)

def check_rate_limit(user_id: int) -> bool:
    """Check if user is within rate limit."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now()
        window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
        
        cursor.execute("SELECT message_count, window_start FROM rate_limits WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            cursor.execute("INSERT INTO rate_limits (user_id, message_count, window_start) VALUES (?, 1, ?)", 
                         (user_id, now))
            conn.commit()
            return True
        
        message_count, stored_window_start = result
        stored_window_start = datetime.fromisoformat(stored_window_start)
        
        if stored_window_start < window_start:
            cursor.execute("UPDATE rate_limits SET message_count = 1, window_start = ? WHERE user_id = ?", 
                         (now, user_id))
            conn.commit()
            return True
        
        if message_count >= RATE_LIMIT_MESSAGES:
            return False
        
        cursor.execute("UPDATE rate_limits SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True

def update_user_info(user: User):
    """Update user information in database."""
    db.add_user(user.id, user.username, user.first_name, user.last_name)

def update_user_activity(user_id: int):
    """Update user's last activity timestamp."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_seen = datetime('now') WHERE user_id = ?", (user_id,))
        conn.commit()

async def broadcast_message(context: ContextTypes.DEFAULT_TYPE, message: str) -> dict:
    """Broadcast message to all registered users."""
    users = db.get_registered_users()
    results = {'success': 0, 'failed': 0}
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user['user_id'], text=message)
            results['success'] += 1
        except (Forbidden, BadRequest):
            results['failed'] += 1
        
        await asyncio.sleep(0.5)
    
    return results

def format_user_info(user_data: dict) -> str:
    """Format user information for display."""
    user_id = user_data['user_id']
    username = user_data.get('username')
    first_name = user_data.get('first_name')
    is_registered = user_data.get('is_registered')
    is_admin_status = user_data.get('is_admin')
    
    display_name = first_name or username or f"User {user_id}"
    if username and first_name:
        display_name += f" (@{username})"
    
    status = ["✅ Terdaftar" if is_registered else "❌ Belum Terdaftar"]
    if is_admin_status:
        status.append("👑 Admin")
    
    return f"👤 {display_name}\n📋 ID: {user_id}\n📊 Status: {' | '.join(status)}\n" + "─" * 30

def split_message(text, max_length=4096):
    """Split long messages into chunks."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + '\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.rstrip())
            current_chunk = line + '\n'
    
    if current_chunk:
        chunks.append(current_chunk.rstrip())
    
    return chunks

def safe_markdown_text(text: str, max_length: int = 4000) -> str:
    """Safely format text for Telegram markdown, with length limiting."""
    if not text:
        return ""
    
    # Escape markdown special characters
    special_chars = ['_', '*', '[', ']', '(', ')', '`']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length-3] + "..."
    
    return text

def chunk_text(text: str, max_length: int = 4000) -> list:
    """Split text into chunks that fit Telegram's message limit."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    lines = text.split('\n')
    current_chunk = []
    current_length = 0
    
    for line in lines:
        line_length = len(line) + 1  # +1 for newline
        
        if current_length + line_length > max_length and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_length = line_length
        else:
            current_chunk.append(line)
            current_length += line_length
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks
