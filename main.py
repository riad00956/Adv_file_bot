import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters, 
    ContextTypes
)

# Import our custom modules
from database import db
from ui import UI
import utils

# ================= CONFIGURATION =================
BOT_TOKEN = "8255821774:AAEOmf1OLvLcZb4NmHHdaGzwROx19q2P9yU"
ADMIN_ID = 7832264582 # Your Telegram ID
FS_CHANNEL = "@rifatsbotz" # Your channel username
# =================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

async def is_maint():
    res = await db.query("SELECT value FROM settings WHERE key='maintenance'", fetchone=True)
    return res['value'] == "1" if res else False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return

    # Register User
    await db.query(
        "INSERT OR IGNORE INTO users (user_id, first_name, username, join_date) VALUES (?,?,?,?)", 
        (user.id, user.first_name, user.username, datetime.now().isoformat()), 
        commit=True
    )
    
    # Maint Check
    if await is_maint() and user.id != ADMIN_ID:
        await update.message.reply_text("🚧 *Bot is under maintenance.*", parse_mode='Markdown')
        return

    # Deep Link
    if context.args:
        if not await utils.force_join(context.bot, user.id, FS_CHANNEL):
            await update.message.reply_text(f"❌ Join {FS_CHANNEL} first!")
            return

        file = await db.query("SELECT * FROM files WHERE file_code=?", (context.args[0],), fetchone=True)
        if file:
            await db.query("UPDATE files SET views = views + 1 WHERE id=?", (file['id'],), commit=True)
            cap = f"📁 `{file['file_name']}`\n⚖️ {utils.format_size(file['file_size'])}"
            if file['file_type'] == 'photo': await update.message.reply_photo(file['file_id'], caption=cap)
            elif file['file_type'] == 'video': await update.message.reply_video(file['file_id'], caption=cap)
            else: await update.message.reply_document(file['file_id'], caption=cap)
            return

    u_data = await db.query("SELECT account_type FROM users WHERE user_id=?", (user.id,), fetchone=True)
    txt, kb = UI.main_menu(u_data['account_type'] if u_data else 'free')
    await update.message.reply_text(txt, reply_markup=kb, parse_mode='Markdown')

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query: return
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data

    if data == "nav_start":
        u_data = await db.query("SELECT account_type FROM users WHERE user_id=?", (user_id,), fetchone=True)
        txt, kb = UI.main_menu(u_data['account_type'] if u_data else 'free')
        await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    elif data == "nav_upload":
        await query.edit_message_text("📤 *Send the file now.*", reply_markup=UI.back_kb(), parse_mode='Markdown')
        context.user_data['state'] = 'upload'

    elif data.startswith("nav_myfiles_"):
        page = int(data.split("_")[2])
        files = await db.query("SELECT * FROM files WHERE owner_id=? ORDER BY id DESC LIMIT 10 OFFSET ?", (user_id, page*10), fetchall=True)
        total = (await db.query("SELECT COUNT(*) as count FROM files WHERE owner_id=?", (user_id,), fetchone=True))['count']
        txt, kb = UI.my_files_list(files, page, total)
        await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    elif data.startswith("view_"):
        f_id = data.split("_")[1]
        file = await db.query("SELECT * FROM files WHERE id=?", (f_id,), fetchone=True)
        if file:
            txt, kb = UI.file_view(file, context.bot.username)
            await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    elif data == "nav_premium":
        await query.edit_message_text("⭐ *Enter Prime Pass Key:*", reply_markup=UI.back_kb(), parse_mode='Markdown')
        context.user_data['state'] = 'redeem'

    elif data == "adm_stats" and user_id == ADMIN_ID:
        u = (await db.query("SELECT COUNT(*) as c FROM users", fetchone=True))['c']
        f = (await db.query("SELECT COUNT(*) as c FROM files", fetchone=True))['c']
        await query.answer(f"Users: {u}\nFiles: {f}", show_alert=True)

    elif data == "adm_gen" and user_id == ADMIN_ID:
        key = utils.gen_prime_key()
        await db.query("INSERT INTO prime_passes (pass_key) VALUES (?)", (key,), commit=True)
        await query.edit_message_text(f"✅ Key: `{key}`", reply_markup=UI.admin_panel(), parse_mode='Markdown')

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != 'upload': return
    msg = update.message
    if not msg: return
    
    file_obj = msg.document or msg.video or (msg.photo[-1] if msg.photo else None)
    if not file_obj: return

    f_id, f_code = file_obj.file_id, utils.gen_code()
    f_name = getattr(file_obj, 'file_name', f"File_{f_code[:4]}")
    f_type = 'photo' if msg.photo else ('video' if msg.video else 'document')
    
    await db.query(
        "INSERT INTO files (file_id, file_type, file_name, file_size, file_code, owner_id, upload_date, expiry_date) VALUES (?,?,?,?,?,?,?,?)",
        (f_id, f_type, f_name, getattr(file_obj, 'file_size', 0), f_code, msg.from_user.id, datetime.now().isoformat(), utils.get_expiry()), 
        commit=True
    )
    
    await msg.delete()
    link = f"https://t.me/{context.bot.username}?start={f_code}"
    await context.bot.send_message(msg.from_user.id, f"✅ *Link:* `{link}`", reply_markup=UI.back_kb(), parse_mode='Markdown')
    context.user_data['state'] = None

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') == 'redeem':
        key = update.message.text.strip()
        check = await db.query("SELECT * FROM prime_passes WHERE pass_key=? AND is_used=0", (key,), fetchone=True)
        await update.message.delete()
        if check:
            await db.query("UPDATE prime_passes SET is_used=1, used_by=? WHERE pass_key=?", (update.effective_user.id, key), commit=True)
            await db.query("UPDATE users SET account_type='premium' WHERE user_id=?", (update.effective_user.id,), commit=True)
            await update.message.reply_text("⭐ *Premium Activated!*")
        else:
            await update.message.reply_text("❌ Invalid Key.")
        context.user_data['state'] = None

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        txt, kb = UI.admin_panel()
        await update.message.reply_text(txt, reply_markup=kb, parse_mode='Markdown')

async def main():
    await db.connect()
    # Fixed for Python 3.13 compatibility
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_files))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot Started...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
