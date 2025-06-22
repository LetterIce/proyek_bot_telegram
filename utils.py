import asyncio
import logging
import functools
from datetime import datetime, timedelta
from typing import List, Callable, Any
from telegram import Update, User
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest
from database import db
from config import RATE_LIMIT_MESSAGES, RATE_LIMIT_WINDOW, ADMIN_ID, ADDITIONAL_ADMINS

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
        
        # Skip rate limiting for admins
        if is_admin(user_id):
            return await func(update, context, *args, **kwargs)
        
        # Check rate limit
        if not check_rate_limit(user_id):
            await update.message.reply_text("⚠️ Anda mengirim pesan terlalu cepat. Silakan tunggu sebentar.")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

def is_admin(user_id: int) -> bool:
    """Check if user is admin (including main admin and additional admins)."""
    return user_id == ADMIN_ID or user_id in ADDITIONAL_ADMINS or db.is_admin(user_id)

def check_rate_limit(user_id: int) -> bool:
    """Check if user is within rate limit."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now()
        window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
        
        cursor.execute("SELECT message_count, window_start FROM rate_limits WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            # First message from user
            cursor.execute("INSERT INTO rate_limits (user_id, message_count, window_start) VALUES (?, 1, ?)", 
                         (user_id, now))
            conn.commit()
            return True
        
        message_count, stored_window_start = result
        stored_window_start = datetime.fromisoformat(stored_window_start)
        
        if stored_window_start < window_start:
            # Reset window
            cursor.execute("UPDATE rate_limits SET message_count = 1, window_start = ? WHERE user_id = ?", 
                         (now, user_id))
            conn.commit()
            return True
        
        if message_count >= RATE_LIMIT_MESSAGES:
            return False
        
        # Increment message count
        cursor.execute("UPDATE rate_limits SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True

def update_user_info(user: User):
    """Update user information in database."""
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

async def safe_send_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs) -> bool:
    """Safely send message with error handling."""
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return True
    except Forbidden:
        logger.warning(f"Cannot send message to {chat_id}: User blocked the bot")
        return False
    except BadRequest as e:
        logger.warning(f"Cannot send message to {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending message to {chat_id}: {e}")
        return False

async def broadcast_message(context: ContextTypes.DEFAULT_TYPE, message: str, user_list: List[int] = None, 
                          delay: float = 0.5) -> dict:
    """Broadcast message to multiple users with detailed results."""
    if user_list is None:
        users = db.get_registered_users()
        user_list = [user['user_id'] for user in users]
    
    results = {
        'success': 0,
        'failed': 0,
        'blocked': 0,
        'not_found': 0,
        'failed_users': []
    }
    
    for user_id in user_list:
        success = await safe_send_message(context, user_id, message)
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
            results['failed_users'].append(user_id)
        
        if delay > 0:
            await asyncio.sleep(delay)
    
    return results

def format_user_info(user_data: dict) -> str:
    """Format user information for display."""
    user_id = user_data['user_id']
    username = user_data.get('username')
    first_name = user_data.get('first_name')
    is_registered = user_data.get('is_registered')
    is_admin_status = user_data.get('is_admin')
    message_count = user_data.get('message_count', 0)
    
    # Build display name
    display_name = first_name or username or f"User {user_id}"
    if username and first_name:
        display_name += f" (@{username})"
    elif username and not first_name:
        display_name = f"@{username}"
    
    # Build status
    status = ["✅ Terdaftar" if is_registered else "❌ Belum Terdaftar"]
    if is_admin_status:
        status.append("👑 Admin")
    
    return f"👤 {display_name}\n📋 ID: {user_id}\n📊 Status: {' | '.join(status)}\n💬 Pesan: {message_count}\n" + "─" * 30

def format_stats(stats: dict) -> str:
    """Format bot statistics for display."""
    text = "📊 **Statistik Bot**\n\n"
    text += f"👥 Total Users: {stats.get('total_users', 0)}\n"
    text += f"✅ Registered Users: {stats.get('registered_users', 0)}\n"
    text += f"👑 Admin Users: {stats.get('admin_users', 0)}\n"
    text += f"💬 Total Messages: {stats.get('total_messages', 0)}\n"
    text += f"🔤 Active Keywords: {stats.get('active_keywords', 0)}\n\n"
    
    top_keywords = stats.get('top_keywords', [])
    if top_keywords:
        text += "🔥 **Top Keywords:**\n"
        for keyword, usage in top_keywords:
            text += f"• `{keyword}`: {usage}x\n"
    
    return text

def split_message(text: str, max_length: int = 4096) -> List[str]:
    """Split long message into chunks."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        
        # Find last newline within limit
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip('\n')
    
    return chunks

def escape_markdown(text: str) -> str:
    """Escape markdown special characters."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
