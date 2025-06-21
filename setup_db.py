import sqlite3

# Nama file database yang akan dibuat
DATABASE_FILE = "bot_database.db"

# Perintah SQL untuk membuat semua tabel
# Disimpan dalam satu string multi-baris untuk kemudahan
SQL_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    is_registered INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT UNIQUE NOT NULL,
    response TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS message_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message_text TEXT,
    response_text TEXT,
    timestamp DATETIME
);
"""

def create_database():
    """Membuat koneksi ke database dan mengeksekusi perintah pembuatan tabel."""
    conn = None
    try:
        # Membuat koneksi. Jika file belum ada, file akan dibuat.
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Menjalankan beberapa statement SQL sekaligus
        cursor.executescript(SQL_CREATE_TABLES)
        
        # Menyimpan perubahan
        conn.commit()
        
        print(f"Database '{DATABASE_FILE}' dan tabel-tabelnya berhasil dibuat atau sudah ada.")
        
    except sqlite3.Error as e:
        print(f"Terjadi error saat membuat database: {e}")
        
    finally:
        # Pastikan koneksi ditutup
        if conn:
            conn.close()

if __name__ == "__main__":
    create_database()