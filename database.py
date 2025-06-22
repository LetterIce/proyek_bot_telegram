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
            
            # Users table with additional fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_registered INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    settings TEXT DEFAULT '{}'
                );
            ''')
            
            # Check and add missing columns to existing users table
            self._migrate_users_table(cursor)
            
            # Enhanced keywords table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT UNIQUE NOT NULL,
                    response TEXT NOT NULL,
                    created_by INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    usage_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );
            ''')
            
            # Migrate keywords table - add missing columns
            self._migrate_keywords_table(cursor)
            
            # Enhanced message history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_text TEXT,
                    response_text TEXT,
                    message_type TEXT DEFAULT 'text',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
            ''')
            
            # Bot statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_name TEXT UNIQUE NOT NULL,
                    stat_value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # Rate limiting
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER PRIMARY KEY,
                    message_count INTEGER DEFAULT 0,
                    window_start DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            conn.commit()
    
    def _migrate_users_table(self, cursor):
        """Add missing columns to users table if they don't exist."""
        # Get existing columns
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Define required columns with their definitions (using constant defaults)
        required_columns = {
            'first_name': 'TEXT',
            'last_name': 'TEXT',
            'is_banned': 'INTEGER DEFAULT 0',
            'join_date': 'TEXT',
            'last_seen': 'TEXT',
            'message_count': 'INTEGER DEFAULT 0',
            'settings': 'TEXT DEFAULT "{}"'
        }
        
        # Add missing columns
        for column_name, column_def in required_columns.items():
            if column_name not in existing_columns:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
                
                # Set default datetime value for datetime columns
                if column_name in ['join_date', 'last_seen']:
                    current_time = datetime.now().isoformat()
                    cursor.execute(f"UPDATE users SET {column_name} = ? WHERE {column_name} IS NULL", (current_time,))
    
    def _migrate_keywords_table(self, cursor):
        """Add missing columns to keywords table if they don't exist."""
        # Get existing columns
        cursor.execute("PRAGMA table_info(keywords)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Add is_active column if it doesn't exist
        if 'is_active' not in existing_columns:
            cursor.execute("ALTER TABLE keywords ADD COLUMN is_active INTEGER DEFAULT 1")
            print("Added is_active column to keywords table")
        
        # Add usage_count column if it doesn't exist
        if 'usage_count' not in existing_columns:
            cursor.execute("ALTER TABLE keywords ADD COLUMN usage_count INTEGER DEFAULT 0")
            print("Added usage_count column to keywords table")
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Add or update user information."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check which columns exist in the table
            cursor.execute("PRAGMA table_info(users)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # Build dynamic query based on existing columns
            base_columns = ['user_id']
            base_values = [user_id]
            
            if 'username' in existing_columns:
                base_columns.append('username')
                base_values.append(username)
            
            if 'first_name' in existing_columns:
                base_columns.append('first_name')
                base_values.append(first_name)
                
            if 'last_name' in existing_columns:
                base_columns.append('last_name')
                base_values.append(last_name)
                
            if 'last_seen' in existing_columns:
                base_columns.append('last_seen')
                base_values.append(datetime.now().isoformat())
            
            # Build and execute query
            columns_str = ', '.join(base_columns)
            placeholders = ', '.join(['?'] * len(base_values))
            
            cursor.execute(f'''
                INSERT OR REPLACE INTO users ({columns_str})
                VALUES ({placeholders})
            ''', base_values)
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
            
            # Check which columns exist before updating
            cursor.execute("PRAGMA table_info(users)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            # Build update query based on existing columns
            update_parts = []
            update_values = []
            
            if 'message_count' in existing_columns:
                update_parts.append("message_count = message_count + 1")
            
            if 'last_seen' in existing_columns:
                update_parts.append("last_seen = ?")
                update_values.append(datetime.now().isoformat())
            
            if update_parts:
                update_query = f"UPDATE users SET {', '.join(update_parts)} WHERE user_id = ?"
                update_values.append(user_id)
                cursor.execute(update_query, update_values)
            
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
            
            # Keyword stats - check which columns exist
            cursor.execute("PRAGMA table_info(keywords)")
            keyword_columns = {row[1] for row in cursor.fetchall()}
            
            try:
                if 'is_active' in keyword_columns:
                    cursor.execute("SELECT COUNT(*) FROM keywords WHERE is_active = 1")
                else:
                    cursor.execute("SELECT COUNT(*) FROM keywords")
                stats['active_keywords'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                cursor.execute("SELECT COUNT(*) FROM keywords")
                stats['active_keywords'] = cursor.fetchone()[0]
            
            # Top keywords - only if usage_count column exists
            try:
                if 'usage_count' in keyword_columns:
                    cursor.execute("SELECT keyword, usage_count FROM keywords ORDER BY usage_count DESC LIMIT 5")
                    stats['top_keywords'] = cursor.fetchall()
                else:
                    cursor.execute("SELECT keyword, 0 as usage_count FROM keywords LIMIT 5")
                    stats['top_keywords'] = cursor.fetchall()
            except sqlite3.OperationalError:
                stats['top_keywords'] = []
            
            return stats

# Global database instance
db = Database()
