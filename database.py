import sqlite3
import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from config import DATABASE_PATH

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
            
            # Users table with all fields from the start
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_registered INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    join_date TEXT DEFAULT (datetime('now')),
                    last_seen TEXT DEFAULT (datetime('now')),
                    message_count INTEGER DEFAULT 0,
                    settings TEXT DEFAULT '{}'
                );
            ''')
            
            # Keywords table with all fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT UNIQUE NOT NULL,
                    response TEXT NOT NULL,
                    created_by INTEGER,
                    created_at TEXT DEFAULT (datetime('now')),
                    usage_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );
            ''')
            
            # Message history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_text TEXT,
                    response_text TEXT,
                    message_type TEXT DEFAULT 'text',
                    timestamp TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
            ''')
            
            # Bot statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_name TEXT UNIQUE NOT NULL,
                    stat_value TEXT NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
            ''')
            
            # Rate limiting
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER PRIMARY KEY,
                    message_count INTEGER DEFAULT 0,
                    window_start TEXT DEFAULT (datetime('now'))
                );
            ''')
            
            conn.commit()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Add or update user information."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_seen)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (user_id, username, first_name, last_name))
            conn.commit()
    
    def register_user(self, user_id: int) -> bool:
        """Register a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_registered = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def is_registered(self, user_id: int) -> bool:
        """Check if user is registered."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_registered FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return bool(result and result[0])
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return bool(result and result[0])
    
    def set_admin(self, user_id: int, is_admin: bool = True):
        """Set admin status for user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (int(is_admin), user_id))
            conn.commit()
    
    def get_all_users(self) -> List[Dict]:
        """Get all users."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_registered_users(self) -> List[Dict]:
        """Get all registered users."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE is_registered = 1")
            return [dict(row) for row in cursor.fetchall()]
    
    def add_keyword(self, keyword: str, response: str, created_by: int) -> bool:
        """Add a new keyword."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO keywords (keyword, response, created_by) VALUES (?, ?, ?)",
                    (keyword.lower(), response, created_by)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_keyword_response(self, keyword: str) -> Optional[str]:
        """Get response for a keyword."""
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
                return result[0]
            return None
    
    def delete_keyword(self, keyword: str) -> bool:
        """Delete a keyword."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM keywords WHERE keyword = ?", (keyword.lower(),))
            conn.commit()
            return cursor.rowcount > 0
    
    def log_message(self, user_id: int, message: str, response: str, message_type: str = 'text'):
        """Log message to history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO message_history (user_id, message_text, response_text, message_type) VALUES (?, ?, ?, ?)",
                (user_id, message, response, message_type)
            )
            cursor.execute(
                "UPDATE users SET message_count = message_count + 1, last_seen = datetime('now') WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
    
    def get_user_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get message history for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM message_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_global_history(self, limit: int = 10) -> List[Dict]:
        """Get global message history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM message_history ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def update_stat(self, stat_name: str, stat_value: str):
        """Update bot statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO bot_stats (stat_name, stat_value, updated_at) VALUES (?, ?, ?)",
                (stat_name, stat_value, datetime.now())
            )
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # User stats
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered = 1")
            stats['registered_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
            stats['admin_users'] = cursor.fetchone()[0]
            
            # Message stats
            cursor.execute("SELECT COUNT(*) FROM message_history")
            stats['total_messages'] = cursor.fetchone()[0]
            
            # Keyword stats
            cursor.execute("SELECT COUNT(*) FROM keywords WHERE is_active = 1")
            stats['active_keywords'] = cursor.fetchone()[0]
            
            # Top keywords
            cursor.execute("SELECT keyword, usage_count FROM keywords ORDER BY usage_count DESC LIMIT 5")
            stats['top_keywords'] = cursor.fetchall()
            
            return stats

# Global database instance
db = Database()
