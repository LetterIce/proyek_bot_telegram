import os
import asyncio
from flask import Flask, request, jsonify
from ai_core import ai_core
from system_info import format_system_stats
from database import db
from utils import broadcast_message
from telegram import Bot
from config import BOT_TOKEN as CONFIG_BOT_TOKEN, ADMIN_ID as CONFIG_ADMIN_ID

# Load sensitive values from environment variables if available
BOT_TOKEN = os.environ.get("BOT_TOKEN", CONFIG_BOT_TOKEN)
ADMIN_ID = os.environ.get("ADMIN_ID", CONFIG_ADMIN_ID)

app = Flask(__name__)

@app.route('/chat', methods=['POST'])
def chat():
    print("Headers:", dict(request.headers))
    print("Data:", request.data)
    print("JSON:", request.get_json())
    data = request.get_json()
    message = data.get('message', '') if data else ''
    user_id = data.get('user_id', None) if data else None  # Accept user_id from client if provided
    if not message:
        return jsonify({'error': 'No message provided'}), 400

    # Check for keyword match first
    keyword_response = db.get_keyword_response(message)
    if keyword_response:
        # Log keyword response if user_id is provided
        if user_id:
            db.log_message(user_id, message, keyword_response, 'keyword')
        return jsonify({'response': keyword_response})

    # If no keyword match, use AI
    response = ai_core.generate_response(message)
    if hasattr(response, '__await__'):
        response = asyncio.run(response)

    # Log AI response if user_id is provided
    if user_id:
        db.log_message(user_id, message, response, 'ai')

    return jsonify({'response': response})

@app.route('/stats', methods=['GET'])
def stats():
    # Get real stats from your bot/database
    users = db.get_all_users()
    registered_users = db.get_registered_users()
    bot_stats = {
        "total_users": len(users),
        "registered_users": len(registered_users),
        "system_stats": format_system_stats()
    }
    return jsonify(bot_stats)

@app.route('/listmembers', methods=['GET'])
def list_members():
    users = db.get_all_users()
    return jsonify(users)

@app.route('/listkeyword', methods=['GET'])
def list_keyword():
    keywords = db.get_all_keywords()
    return jsonify(keywords)

@app.route('/myhistory', methods=['GET'])
def my_history():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    history = db.get_user_history(user_id, 20)
    return jsonify(history)

@app.route('/history', methods=['GET'])
def history():
    user_id = request.args.get('user_id', type=int)
    if user_id:
        history = db.get_user_history(user_id, 20)
    else:
        history = db.get_global_history(20)
    return jsonify(history)

@app.route('/broadcast', methods=['POST'])
def broadcast():
    data = request.get_json()
    message = data.get('message', '')
    if not message:
        return jsonify({'error': 'No message provided'}), 400

    bot = Bot(token=BOT_TOKEN)
    users = [user for user in db.get_registered_users() if user.get('is_registered', 0) == 1 and user.get('is_banned', 0) == 0]
    user_ids = [user.get('user_id') for user in users]
    print(f"Broadcasting to user_ids: {user_ids}")  # Log user IDs

    async def send_all():
        results = {'success': 0, 'failed': 0, 'errors': []}
        for user in users:
            chat_id = user.get('user_id')
            try:
                await bot.send_message(chat_id=chat_id, text=message)
                results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                error_msg = str(e)
                print(f"Failed to send to {chat_id}: {error_msg}")  # Log error
                results['errors'].append({'user_id': chat_id, 'error': error_msg})
        return results

    results = asyncio.run(send_all())
    return jsonify({
        'status': 'broadcast finished',
        'success': results['success'],
        'failed': results['failed'],
        'total': len(users),
        'errors': results['errors'],
        'user_ids': user_ids  # Return for debugging
    })

@app.route('/aistatus', methods=['GET'])
def aistatus():
    status = "✅ AI Core: Aktif" if ai_core.is_available() else "❌ AI Core: Nonaktif"
    config_status = f"🔧 AI Diaktifkan: {'Ya' if getattr(ai_core, 'api_key', None) else 'Tidak'}"
    model_name = getattr(ai_core, 'model_name', 'Tidak diketahui')
    return jsonify({
        "status": status,
        "config_status": config_status,
        "model_name": model_name
    })

@app.route('/delkeyword', methods=['POST'])
def del_keyword():
    data = request.get_json()
    keyword = data.get('keyword', '')
    if not keyword:
        return jsonify({'error': 'No keyword provided'}), 400
    result = db.delete_keyword(keyword)
    return jsonify({'success': result})

@app.route('/start', methods=['GET'])
def start():
    user_id = request.args.get('user_id', type=int)
    first_name = request.args.get('first_name', 'Pengguna')
    if user_id:
        db.update_user_info(user_id, first_name=first_name)
    welcome_text = (
        f"👋 Halo, {user.first_name}! Senang bertemu dengan Anda.\n\n"
        "Saya adalah bot AI yang siap menjadi teman diskusi Anda.\n"
        "Silahkan registrasi dengan perintah /register untuk mulai menggunakan bot.\n\n"
    )
    return jsonify({"message": welcome_text})

@app.route('/conversation', methods=['GET'])
def conversation():
    user_id = request.args.get('user_id', type=int)
    args = request.args.getlist('arg')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    # If no args, show current settings
    if not args:
        enabled = db.is_context_enabled(user_id)
        limit = db.get_user_context_limit(user_id)
        context_history = db.get_conversation_context(user_id)
        status = "🟢 Aktif" if enabled else "🔴 Nonaktif"
        settings_text = (
            f"⚙️ Pengaturan Percakapan:\n\n"
            f"📝 Status Memori: {status}\n"
            f"📊 Batas Pesan: {limit} pesan\n"
            f"💬 Pesan Tersimpan: {len(context_history)} pesan\n\n"
            f"Cara Penggunaan:\n"
            f"/conversation on - Aktifkan memori\n"
            f"/conversation off - Nonaktifkan memori\n"
            f"/conversation limit <angka> - Atur batas pesan (1-50)\n"
            f"/clearconversation - Hapus riwayat percakapan"
        )
        return jsonify({
            "status": status,
            "enabled": enabled,
            "limit": limit,
            "history_count": len(context_history),
            "history": context_history,
            "settings_text": settings_text
        })

    # Handle arguments: on, off, limit <angka>
    command = args[0].lower()
    if command == "on":
        db.set_user_context_settings(user_id, enabled=True)
        return jsonify({"success": True, "message": "✅ Memori percakapan diaktifkan! Bot akan mengingat percakapan sebelumnya."})
    elif command == "off":
        db.set_user_context_settings(user_id, enabled=False)
        return jsonify({"success": True, "message": "❌ Memori percakapan dinonaktifkan. Bot tidak akan mengingat percakapan sebelumnya."})
    elif command == "limit":
        if len(args) < 2:
            return jsonify({"success": False, "message": "❌ Format: /conversation limit <angka>. Contoh: /conversation limit 15"})
        try:
            new_limit = int(args[1])
            if new_limit < 1 or new_limit > 50:
                return jsonify({"success": False, "message": "❌ Batas pesan harus antara 1-50."})
            current_enabled = db.is_context_enabled(user_id)
            db.set_user_context_settings(user_id, enabled=current_enabled, max_messages=new_limit)
            return jsonify({"success": True, "message": f"✅ Batas pesan percakapan diatur ke {new_limit} pesan."})
        except ValueError:
            return jsonify({"success": False, "message": "❌ Angka tidak valid."})
    else:
        return jsonify({"success": False, "message": "❌ Perintah tidak dikenal. Gunakan: on, off, atau limit <angka>."})

@app.route('/clearconversation', methods=['POST'])
def clear_conversation():
    data = request.get_json()
    user_id = data.get('user_id', None)
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    result = db.clear_conversation_context(user_id)
    if result:
        return jsonify({
            "success": True,
            "message": "🗑️ Riwayat percakapan Anda telah dihapus.\nPercakapan baru akan dimulai tanpa konteks sebelumnya."
        })
    else:
        return jsonify({
            "success": False,
            "message": "❌ Gagal menghapus riwayat percakapan."
        })

@app.route('/addadmin', methods=['POST'])
def add_admin():
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'No user_id provided'}), 400
    try:
        user_id_int = int(user_id)
        db.set_admin(user_id_int, True)
        return jsonify({'success': True, 'message': f'User {user_id} sekarang adalah admin.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Gagal menambah admin: {str(e)}'})

if __name__ == '__main__':
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    app.run(host=host, port=port)
