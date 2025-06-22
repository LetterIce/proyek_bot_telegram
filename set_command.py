import asyncio
from telegram import Bot, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat
from config import BOT_TOKEN, ADMIN_ID, GEMINI_ENABLED

# --- DAFTAR PERINTAH ---

# Perintah untuk semua pengguna
commands_for_all = [
    BotCommand("start", "▶️ Memulai bot"),
    BotCommand("register", "✍️ Mendaftar sebagai member"),
    BotCommand("help", "❓ Menampilkan bantuan"),
    BotCommand("conversation", "⚙️ Pengaturan memori percakapan"),
    BotCommand("clearconversation", "🗑️ Hapus riwayat percakapan"),
    BotCommand("myhistory", "📜 Lihat riwayat percakapan Anda"),
]

# Perintah tambahan khusus untuk admin
commands_for_admin = [
    # Termasuk perintah umum agar tidak hilang
    *commands_for_all, 
    BotCommand("addkeyword", "➕ Tambah keyword & jawaban"),
    BotCommand("delkeyword", "➖ Hapus keyword"),
    BotCommand("listkeyword", "📝 Lihat semua keyword"),
    BotCommand("listmembers", "👥 Lihat daftar member"),
    BotCommand("broadcast", "📢 Kirim pesan ke semua member"),
    BotCommand("addadmin", "👑 Tambah admin baru"),
    BotCommand("history", "📜 Lihat riwayat pesan"),
    BotCommand("stats", "📊 Lihat statistik bot"),
]

# Add AI status command only if Gemini is enabled
if GEMINI_ENABLED:
    commands_for_admin.append(BotCommand("aistatus", "🧠 Cek status AI"))

async def set_bot_commands():
    """
    Fungsi async untuk mengatur daftar perintah bot di Telegram.
    """
    bot = Bot(token=BOT_TOKEN)
    async with bot:
        # 1. Atur perintah default untuk semua pengguna private chat
        await bot.set_my_commands(
            commands=commands_for_all,
            scope=BotCommandScopeAllPrivateChats()
        )
        print("✅ Perintah umum berhasil diatur untuk semua pengguna.")

        # 2. Atur perintah khusus untuk chat admin
        # Ini akan menimpa daftar perintah umum HANYA untuk Anda (admin)
        await bot.set_my_commands(
            commands=commands_for_admin,
            scope=BotCommandScopeChat(chat_id=ADMIN_ID)
        )
        print(f"✅ Perintah admin berhasil diatur untuk user ID: {ADMIN_ID}.")

        # 3. Display all commands for verification
        print("\n📝 Daftar perintah yang telah diatur:")
        print("👥 Perintah untuk semua user:")
        for cmd in commands_for_all:
            print(f"  /{cmd.command} - {cmd.description}")
        
        print(f"\n👑 Perintah tambahan untuk admin (ID: {ADMIN_ID}):")
        admin_only_commands = [cmd for cmd in commands_for_admin if cmd not in commands_for_all]
        for cmd in admin_only_commands:
            print(f"  /{cmd.command} - {cmd.description}")

if __name__ == '__main__':
    print("🤖 Mengatur perintah bot...")
    # Jalankan fungsi async menggunakan asyncio.run()
    asyncio.run(set_bot_commands())
    print("✅ Selesai!")