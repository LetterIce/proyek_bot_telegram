import asyncio
from telegram import Bot, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat
from config import BOT_TOKEN, ADMIN_ID

# --- DAFTAR PERINTAH ---

# Perintah untuk semua pengguna
commands_for_all = [
    BotCommand("start", "▶️ Memulai bot"),
    BotCommand("register", "✍️ Mendaftar sebagai member"),
    BotCommand("help", "❓ Menampilkan bantuan"),
]

# Perintah tambahan khusus untuk admin
commands_for_admin = [
    # Termasuk perintah umum agar tidak hilang
    *commands_for_all, 
    BotCommand("addkeyword", "➕ Tambah keyword & jawaban"),
    BotCommand("delkeyword", "➖ Hapus keyword"),
    BotCommand("listmembers", "👥 Lihat daftar member"),
    BotCommand("broadcast", "📢 Kirim pesan ke semua member"),
    BotCommand("addadmin", "👑 Tambah admin baru"),
    BotCommand("history", "📜 Lihat riwayat pesan")
]

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


if __name__ == '__main__':
    print("Mengatur perintah bot...")
    # Jalankan fungsi async menggunakan asyncio.run()
    asyncio.run(set_bot_commands())
    print("Selesai!")