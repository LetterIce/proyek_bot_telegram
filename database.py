import sqlite3
import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.setup_database()
        logger.info("Database initialized successfully")
    
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
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (created_by) REFERENCES users (user_id)
                );
            ''')
            
            # Message history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',
                    timestamp TEXT NOT NULL,
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
                    window_start TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
            ''')
            
            # Migrate existing tables
            self._migrate_tables()
            
            conn.commit()
            logger.info("Database tables created/verified successfully")

    def _migrate_tables(self):
        """Migrate existing tables to add missing columns."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if message_type column exists in message_history
                cursor.execute("PRAGMA table_info(message_history)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'message_type' not in columns:
                    logger.info("Adding message_type column to message_history table")
                    cursor.execute("ALTER TABLE message_history ADD COLUMN message_type TEXT DEFAULT 'text'")
                
                # Update any existing records that have NULL message_type
                cursor.execute("UPDATE message_history SET message_type = 'text' WHERE message_type IS NULL")
                
                conn.commit()
                logger.info("Database migration completed successfully")
                
        except Exception as e:
            logger.error(f"Error during database migration: {e}")

    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Add or update user information without affecting registration status."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if user exists
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    # Update existing user info without changing registration status
                    cursor.execute('''
                        UPDATE users 
                        SET username = ?, first_name = ?, last_name = ?, last_seen = datetime('now')
                        WHERE user_id = ?
                    ''', (username, first_name, last_name, user_id))
                else:
                    # Insert new user
                    cursor.execute('''
                        INSERT INTO users (user_id, username, first_name, last_name, join_date, last_seen)
                        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                    ''', (user_id, username, first_name, last_name))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding/updating user: {e}")
            return False

    def update_user_activity(self, user_id: int):
        """Update user's last seen timestamp."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET last_seen = datetime('now') WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating user activity: {e}")

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
            logger.error(f"Error checking registration: {e}")
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
            logger.error(f"Error checking admin status: {e}")
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
            logger.error(f"Error setting admin status: {e}")
            return False
    
    def get_all_users(self) -> List[Dict]:
        """Get all users."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    def get_registered_users(self) -> List[Dict]:
        """Get all registered users."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE is_registered = 1")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting registered users: {e}")
            return []
    
    def add_keyword(self, keyword: str, response: str, created_by: int) -> bool:
        """Add a new keyword."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO keywords (keyword, response, created_by, created_at) VALUES (?, ?, ?, ?)",
                    (keyword.lower(), response, created_by, datetime.now().isoformat())
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            logger.error(f"Error adding keyword: {e}")
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
                    return result[0]
                return None
        except Exception as e:
            logger.error(f"Error getting keyword response: {e}")
            return None
    
    def delete_keyword(self, keyword: str) -> bool:
        """Delete a keyword."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM keywords WHERE keyword = ?", (keyword.lower(),))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting keyword: {e}")
            return False
    
    def log_message(self, user_id: int, message_text: str, response_text: str, message_type: str = 'text'):
        """Log message interaction to database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # First ensure the user exists without affecting registration
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if not cursor.fetchone():
                    # Add user if they don't exist (but not registered by default)
                    cursor.execute("""
                        INSERT INTO users (user_id, join_date, last_seen) 
                        VALUES (?, datetime('now'), datetime('now'))
                    """, (user_id,))
                else:
                    # Just update last seen for existing users
                    cursor.execute("""
                        UPDATE users SET last_seen = datetime('now') WHERE user_id = ?
                    """, (user_id,))
                
                # Insert message log
                cursor.execute("""
                    INSERT INTO message_history 
                    (user_id, message_text, response_text, message_type, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, message_text, response_text, message_type, datetime.now().isoformat()))
                
                # Update message count for user
                cursor.execute("""
                    UPDATE users SET message_count = message_count + 1 
                    WHERE user_id = ?
                """, (user_id,))
                
                conn.commit()
                logger.info(f"Message logged successfully for user {user_id}: {message_text[:30]}...")
                
                # Update total messages stat
                self.update_stat('total_messages', str(self.get_total_message_count()))
                return True
                
        except Exception as e:
            logger.error(f"Error logging message for user {user_id}: {e}")
            # Log the full error for debugging
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False
    
    def get_user_history(self, user_id: int, limit: int = 10):
        """Get message history for specific user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # First check if message_type column exists
                cursor.execute("PRAGMA table_info(message_history)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'message_type' in columns:
                    cursor.execute("""
                        SELECT user_id, message_text, response_text, message_type, timestamp
                        FROM message_history 
                        WHERE user_id = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (user_id, limit))
                else:
                    # Fallback for tables without message_type column
                    cursor.execute("""
                        SELECT user_id, message_text, response_text, 'text' as message_type, timestamp
                        FROM message_history 
                        WHERE user_id = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (user_id, limit))
                
                columns = [description[0] for description in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                logger.info(f"Retrieved {len(results)} history records for user {user_id}")
                return results
        except Exception as e:
            logger.error(f"Error getting user history for {user_id}: {e}")
            return []
    
    def get_global_history(self, limit: int = 10):
        """Get global message history."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # First check if message_type column exists
                cursor.execute("PRAGMA table_info(message_history)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'message_type' in columns:
                    cursor.execute("""
                        SELECT user_id, message_text, response_text, message_type, timestamp
                        FROM message_history 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (limit,))
                else:
                    # Fallback for tables without message_type column
                    cursor.execute("""
                        SELECT user_id, message_text, response_text, 'text' as message_type, timestamp
                        FROM message_history 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (limit,))
                
                columns = [description[0] for description in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                logger.info(f"Retrieved {len(results)} global history records")
                return results
        except Exception as e:
            logger.error(f"Error getting global history: {e}")
            return []
    
    def get_total_message_count(self):
        """Get total number of messages."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM message_history")
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            logger.error(f"Error getting message count: {e}")
            return 0
    
    def update_stat(self, stat_name: str, stat_value: str):
        """Update bot statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO bot_stats (stat_name, stat_value, updated_at) VALUES (?, ?, ?)",
                    (stat_name, stat_value, datetime.now().isoformat())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating stat: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        try:
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
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def get_all_stats(self):
        """Get all statistics - compatibility method."""
        return self.get_stats()

# Global database instance
db = Database()
