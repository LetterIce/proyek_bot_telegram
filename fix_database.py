"""Fix database schema by adding missing columns."""

import sqlite3
import logging
from datetime import datetime
from config import DATABASE_PATH

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_database_schema():
    """Fix the database schema by adding missing columns."""
    print("🔧 Fixing database schema...")
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Check current keywords table structure
        cursor.execute("PRAGMA table_info(keywords)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns in keywords table: {columns}")
        
        # Add missing columns one by one with simple defaults
        if 'created_by' not in columns:
            print("Adding created_by column...")
            cursor.execute("ALTER TABLE keywords ADD COLUMN created_by INTEGER DEFAULT 0")
        
        if 'created_at' not in columns:
            print("Adding created_at column...")
            # Use a simple string default, then update with actual datetime
            cursor.execute("ALTER TABLE keywords ADD COLUMN created_at TEXT DEFAULT ''")
            # Update all existing records with current datetime
            current_time = datetime.now().isoformat()
            cursor.execute("UPDATE keywords SET created_at = ? WHERE created_at = ''", (current_time,))
        
        # Commit the schema changes
        conn.commit()
        
        # Update any NULL or empty values
        print("Updating default values...")
        current_time = datetime.now().isoformat()
        cursor.execute("UPDATE keywords SET created_at = ? WHERE created_at IS NULL OR created_at = ''", (current_time,))
        cursor.execute("UPDATE keywords SET usage_count = 0 WHERE usage_count IS NULL")
        cursor.execute("UPDATE keywords SET is_active = 1 WHERE is_active IS NULL")
        cursor.execute("UPDATE keywords SET created_by = 0 WHERE created_by IS NULL")
        
        conn.commit()
        
        # Verify the fix
        cursor.execute("PRAGMA table_info(keywords)")
        new_columns = [column[1] for column in cursor.fetchall()]
        print(f"Updated columns in keywords table: {new_columns}")
        
        # Show existing keywords
        cursor.execute("SELECT keyword, response, usage_count, created_at, created_by FROM keywords LIMIT 5")
        rows = cursor.fetchall()
        print(f"Sample keywords in database: {len(rows)} found")
        for row in rows:
            print(f"  - Keyword: {row[0]}, Response: {row[1][:30]}..., Usage: {row[2]}, Created: {row[3][:19]}, By: {row[4]}")
        
        # Test adding a new keyword
        print("\nTesting keyword operations...")
        try:
            cursor.execute("INSERT INTO keywords (keyword, response, created_by, created_at) VALUES (?, ?, ?, ?)",
                         ("test_fix", "This is a test after fix", 123456, current_time))
            conn.commit()
            print("✅ Test keyword added successfully")
            
            # Clean up test keyword
            cursor.execute("DELETE FROM keywords WHERE keyword = 'test_fix'")
            conn.commit()
            print("✅ Test keyword removed")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
        
        conn.close()
        print("✅ Database schema fixed successfully!")
        
    except Exception as e:
        print(f"❌ Error fixing database: {e}")
        logger.error(f"Database fix error: {e}")

if __name__ == "__main__":
    fix_database_schema()
