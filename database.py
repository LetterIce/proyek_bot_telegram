import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.setup_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def setup_database(self):
        """Initialize database with all required tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_registered INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0,
                    join_date TEXT DEFAULT (datetime('now')),
                    last_seen TEXT DEFAULT (datetime('now')),
                    message_count INTEGER DEFAULT 0
                );
            ''')
            
            # Keywords table with proper schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT UNIQUE NOT NULL,
                    response TEXT NOT NULL,
                    created_by INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    usage_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );
            ''')
            
            # Check and migrate keywords table if needed
            self._migrate_keywords_table(cursor)
            
            # Message history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',
                    timestamp TEXT NOT NULL
                );
            ''')
            
            # Rate limits table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER PRIMARY KEY,
                    message_count INTEGER DEFAULT 0,
                    window_start TEXT DEFAULT (datetime('now'))
                );
            ''')
            
            # Conversation context table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversation_context (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    context_window INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
            ''')
            
            # User conversation settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_conversation_settings (
                    user_id INTEGER PRIMARY KEY,
                    context_enabled INTEGER DEFAULT 1,
                    max_context_messages INTEGER DEFAULT 10,
                    last_context_clear TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
            ''')
            
            conn.commit()
            logger.info("Database setup completed successfully")

    def _migrate_keywords_table(self, cursor):
        """Migrate keywords table to add missing columns."""
        try:
            # Get current table structure
            cursor.execute("PRAGMA table_info(keywords)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add missing columns
            if 'created_by' not in columns:
                logger.info("Adding created_by column to keywords table")
                cursor.execute("ALTER TABLE keywords ADD COLUMN created_by INTEGER DEFAULT 0")
            
            if 'created_at' not in columns:
                logger.info("Adding created_at column to keywords table")
                # Use empty string default, then update with actual datetime
                cursor.execute("ALTER TABLE keywords ADD COLUMN created_at TEXT DEFAULT ''")
                # Update existing records with current datetime
                current_time = datetime.now().isoformat()
                cursor.execute("UPDATE keywords SET created_at = ? WHERE created_at = ''", (current_time,))
            
            if 'usage_count' not in columns:
                logger.info("Adding usage_count column to keywords table")
                cursor.execute("ALTER TABLE keywords ADD COLUMN usage_count INTEGER DEFAULT 0")
            
            if 'is_active' not in columns:
                logger.info("Adding is_active column to keywords table")
                cursor.execute("ALTER TABLE keywords ADD COLUMN is_active INTEGER DEFAULT 1")
            
            # Update any NULL values
            cursor.execute("UPDATE keywords SET created_at = ? WHERE created_at IS NULL OR created_at = ''", (datetime.now().isoformat(),))
            cursor.execute("UPDATE keywords SET usage_count = 0 WHERE usage_count IS NULL")
            cursor.execute("UPDATE keywords SET is_active = 1 WHERE is_active IS NULL")
            cursor.execute("UPDATE keywords SET created_by = 0 WHERE created_by IS NULL")
                
        except Exception as e:
            logger.error(f"Error migrating keywords table: {e}")

    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Add or update user information."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                
                if cursor.fetchone():
                    cursor.execute('''
                        UPDATE users 
                        SET username = ?, first_name = ?, last_name = ?, last_seen = datetime('now')
                        WHERE user_id = ?
                    ''', (username, first_name, last_name, user_id))
                else:
                    cursor.execute('''
                        INSERT INTO users (user_id, username, first_name, last_name)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, username, first_name, last_name))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding/updating user: {e}")
            return False

    def register_user(self, user_id: int) -> bool:
        """Register a user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return False
    
    def is_registered(self, user_id: int) -> bool:
        """Check if user is registered."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_registered FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return bool(result and result[0])
        except Exception as e:
            return False
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return bool(result and result[0])
        except Exception as e:
            return False
    
    def set_admin(self, user_id: int, is_admin: bool = True):
        """Set admin status for user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (int(is_admin), user_id))
                conn.commit()
                return True
        except Exception as e:
            return False
    
    def get_all_users(self) -> List[Dict]:
        """Get all users."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            return []
    
    def get_registered_users(self) -> List[Dict]:
        """Get all registered users."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE is_registered = 1")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            return []
    
    def add_keyword(self, keyword: str, response: str, created_by: int) -> bool:
        """Add a new keyword."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()
                cursor.execute(
                    "INSERT INTO keywords (keyword, response, created_by, created_at) VALUES (?, ?, ?, ?)",
                    (keyword.lower(), response, created_by, current_time)
                )
                conn.commit()
                logger.info(f"Keyword '{keyword}' added successfully by user {created_by}")
                return True
        except sqlite3.IntegrityError as e:
            logger.error(f"Keyword '{keyword}' already exists: {e}")
            return False
        except Exception as e:
            logger.error(f"Error adding keyword '{keyword}': {e}")
            return False
    
    def get_keyword_response(self, keyword: str) -> Optional[str]:
        """Get response for a keyword."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response FROM keywords WHERE keyword = ? AND is_active = 1",
                    (keyword.lower(),)
                )
                result = cursor.fetchone()
                if result:
                    # Update usage count
                    cursor.execute(
                        "UPDATE keywords SET usage_count = usage_count + 1 WHERE keyword = ?",
                        (keyword.lower(),)
                    )
                    conn.commit()
                    logger.debug(f"Keyword '{keyword}' found and usage count updated")
                    return result[0]
                logger.debug(f"Keyword '{keyword}' not found")
                return None
        except Exception as e:
            logger.error(f"Error getting keyword response for '{keyword}': {e}")
            return None
    
    def delete_keyword(self, keyword: str) -> bool:
        """Delete a keyword."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # First check if keyword exists
                cursor.execute("SELECT id FROM keywords WHERE keyword = ?", (keyword.lower(),))
                if not cursor.fetchone():
                    logger.warning(f"Keyword '{keyword}' not found for deletion")
                    return False
                
                # Delete the keyword
                cursor.execute("DELETE FROM keywords WHERE keyword = ?", (keyword.lower(),))
                conn.commit()
                logger.info(f"Keyword '{keyword}' deleted successfully")
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting keyword '{keyword}': {e}")
            return False
    
    def log_message(self, user_id: int, message_text: str, response_text: str, message_type: str = 'normal', file_info: dict = None) -> bool:
        """Log a message interaction."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Add file info to message text if present
                full_message = message_text
                if file_info:
                    file_type = file_info.get('type', 'file')
                    file_name = file_info.get('name', 'unknown')
                    full_message = f"[{file_type.upper()}] {file_name}: {message_text}"
                
                current_time = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO message_history (user_id, message_text, response_text, message_type, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, full_message, response_text, message_type, current_time))
                conn.commit()
                logger.debug(f"Logged message for user {user_id}: {message_type}")
                return True
        except Exception as e:
            logger.error(f"Error logging message: {e}")
            return False

    def get_user_history(self, user_id: int, limit: int = 10):
        """Get message history for specific user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, message_text, response_text, message_type, timestamp
                    FROM message_history 
                    WHERE user_id = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (user_id, limit))
                
                results = cursor.fetchall()
                history = []
                for row in results:
                    history.append({
                        'user_id': row[0],
                        'message_text': row[1],
                        'response_text': row[2],
                        'message_type': row[3],
                        'timestamp': row[4]
                    })
                return history
        except Exception as e:
            logger.error(f"Error getting user history: {e}")
            return []
    
    def get_global_history(self, limit: int = 20):
        """Get global message history."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, message_text, response_text, message_type, timestamp
                    FROM message_history 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                
                results = cursor.fetchall()
                history = []
                for row in results:
                    history.append({
                        'user_id': row[0],
                        'message_text': row[1],
                        'response_text': row[2],
                        'message_type': row[3],
                        'timestamp': row[4]
                    })
                return history
        except Exception as e:
            logger.error(f"Error getting global history: {e}")
            return []

    def get_all_keywords(self) -> List[Dict]:
        """Get all keywords with their information."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT keyword, response, usage_count, created_at, is_active, created_by
                    FROM keywords 
                    WHERE is_active = 1
                    ORDER BY usage_count DESC, keyword ASC
                """)
                
                columns = [description[0] for description in cursor.description]
                result = [dict(zip(columns, row)) for row in cursor.fetchall()]
                logger.info(f"Retrieved {len(result)} keywords from database")
                return result
        except Exception as e:
            logger.error(f"Error getting keywords: {e}")
            return []

    def get_user_message_count(self, user_id: int) -> int:
        """Get total message count for a user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT message_count FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting user message count: {e}")
            return 0
    
    def increment_user_message_count(self, user_id: int):
        """Increment user's message count."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error incrementing message count: {e}")

    def add_conversation_message(self, user_id: int, message_text: str, response_text: str, file_info: dict = None) -> bool:
        """Add a message to conversation context."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get user's max context setting
                max_context = self.get_user_context_limit(user_id)
                
                # Add file info to message text if present
                full_message = message_text
                if file_info:
                    file_type = file_info.get('type', 'file')
                    file_name = file_info.get('name', 'unknown')
                    full_message = f"[{file_type.upper()}] {file_name}: {message_text}"
                
                # Add new message with current timestamp
                current_time = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO conversation_context (user_id, message_text, response_text, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (user_id, full_message, response_text, current_time))
                
                # Clean up old messages beyond limit
                cursor.execute("""
                    DELETE FROM conversation_context 
                    WHERE user_id = ? AND id NOT IN (
                        SELECT id FROM conversation_context 
                        WHERE user_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    )
                """, (user_id, user_id, max_context))
                
                conn.commit()
                logger.debug(f"Added conversation message for user {user_id}: {full_message[:50]}...")
                return True
        except Exception as e:
            logger.error(f"Error adding conversation message: {e}")
            return False
    
    def get_conversation_context(self, user_id: int, limit: int = None) -> List[Dict]:
        """Get conversation context for a user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if limit is None:
                    limit = self.get_user_context_limit(user_id)
                
                cursor.execute("""
                    SELECT message_text, response_text, timestamp
                    FROM conversation_context 
                    WHERE user_id = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (user_id, limit))
                
                results = cursor.fetchall()
                conversations = []
                
                for row in results:
                    conversations.append({
                        'message_text': row[0],
                        'response_text': row[1], 
                        'timestamp': row[2]
                    })
                
                return conversations
        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return []
    
    def clear_conversation_context(self, user_id: int) -> bool:
        """Clear conversation context for a user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM conversation_context WHERE user_id = ?", (user_id,))
                cursor.execute("""
                    INSERT OR REPLACE INTO user_conversation_settings (user_id, last_context_clear)
                    VALUES (?, datetime('now'))
                """, (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error clearing conversation context: {e}")
            return False
    
    def get_user_context_limit(self, user_id: int) -> int:
        """Get user's context message limit."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT max_context_messages FROM user_conversation_settings WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                return result[0] if result else 10
        except Exception as e:
            return 10
    
    def set_user_context_settings(self, user_id: int, enabled: bool = True, max_messages: int = 10) -> bool:
        """Set user's conversation context settings."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO user_conversation_settings 
                    (user_id, context_enabled, max_context_messages)
                    VALUES (?, ?, ?)
                """, (user_id, int(enabled), max_messages))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting context settings: {e}")
            return False
    
    def is_context_enabled(self, user_id: int) -> bool:
        """Check if conversation context is enabled for user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT context_enabled FROM user_conversation_settings WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                return bool(result[0]) if result else True  # Default enabled
        except Exception as e:
            return True

    def get_conversation_history(self, user_id: int, limit: int = 10):
        """Get conversation history for a user with limit."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT message_text, response_text, timestamp, 'conversation' as message_type
                    FROM conversation_context 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (user_id, limit))
                
                results = cursor.fetchall()
                conversations = []
                for row in results:
                    conversations.append({
                        'message_text': row[0],
                        'response_text': row[1],
                        'timestamp': row[2],
                        'message_type': row[3]
                    })
                
                return conversations
                
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []

# Global database instance
db = Database()
