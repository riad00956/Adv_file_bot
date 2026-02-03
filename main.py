import logging
import asyncio
import sys
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

# Custom modules
from database import db
from ui import UI
import utils

# ================= CONFIGURATION =================
BOT_TOKEN = "8255821774:AAEOmf1OLvLcZb4NmHHdaGzwROx19q2P9yU"
ADMIN_ID = 7832264582 
FS_CHANNEL = "@rifatsbotz" 
# =================================================

logging.basicConfig(level=logging.INFO)

async def is_maint():
    try:
        res = await db.query("SELECT value FROM settings WHERE key='maintenance'", fetchone=True)
        return res and res.get('value') == "1"
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return

    await db.query(
        "INSERT OR IGNORE INTO users (user_id, first_name, username, join_date) VALUES (?,?,?,?)", 
        (user.id, user.first_name, user.username, datetime.now().isoformat()), 
        commit=True
    )
    
    if await is_maint() and user.id != ADMIN_ID:
        await update.message.reply_text("🚧 *Bot is under maintenance.*", parse_mode='Markdown')
        return

    if context.args:
        if not await utils.force_join(context.bot, user.id, FS_CHANNEL):
            await update.message.reply_text(f"❌ Join {FS_CHANNEL} first to access the file!")
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
        await query.edit_message_text("📤 *Send the file now (Photo/Video/Doc).* \n_Up to 2GB._", reply_markup=UI.back_kb(), parse_mode='Markdown')
        context.user_data['state'] = 'upload'

    elif data.startswith("nav_myfiles_"):
        page = int(data.split("_")[2])
        files = await db.query("SELECT * FROM files WHERE owner_id=? ORDER BY id DESC LIMIT 10 OFFSET ?", (user_id, page*10), fetchall=True)
        count_res = await db.query("SELECT COUNT(*) as count FROM files WHERE owner_id=?", (user_id,), fetchone=True)
        total = count_res['count'] if count_res else 0
        txt, kb = UI.my_files_list(files, page, total)
        await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    elif data.startswith("view_"):
        f_id = data.split("_")[1]
        file = await db.query("SELECT * FROM files WHERE id=?", (f_id,), fetchone=True)
        if file:
            txt, kb = UI.file_view(file, context.bot.username)
            await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    elif data == "nav_premium":
        await query.edit_message_text("⭐ *Enter Your Prime Pass Key:*", reply_markup=UI.back_kb(), parse_mode='Markdown')
        context.user_data['state'] = 'redeem'

    elif data == "adm_stats" and user_id == ADMIN_ID:
        u = (await db.query("SELECT COUNT(*) as c FROM users", fetchone=True))['c']
        f = (await db.query("SELECT COUNT(*) as c FROM files", fetchone=True))['c']
        await query.answer(f"Users: {u} | Files: {f}", show_alert=True)

    elif data == "adm_gen" and user_id == ADMIN_ID:
        key = utils.gen_prime_key()
        await db.query("INSERT INTO prime_passes (pass_key) VALUES (?)", (key,), commit=True)
        adm_text, adm_kb = UI.admin_panel()
        await query.edit_message_text(f"✅ *Key:* `{key}`\n\n{adm_text}", reply_markup=adm_kb, parse_mode='Markdown')

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != 'upload': return
    msg = update.message
    file_obj = msg.document or msg.video or (msg.photo[-1] if msg.photo else None)
    
    if file_obj:
        f_code = utils.gen_code()
        f_name = getattr(file_obj, 'file_name', f"File_{f_code[:4]}")
        f_type = 'photo' if msg.photo else ('video' if msg.video else 'document')
        
        await db.query(
            "INSERT INTO files (file_id, file_type, file_name, file_size, file_code, owner_id, upload_date) VALUES (?,?,?,?,?,?,?)",
            (file_obj.file_id, f_type, f_name, getattr(file_obj, 'file_size', 0), f_code, msg.from_user.id, datetime.now().isoformat()), 
            commit=True
        )
        
        link = f"https://t.me/{context.bot.username}?start={f_code}"
        await msg.reply_text(f"✅ *File Saved!*\n\n🔗 *Link:* `{link}`", reply_markup=UI.back_kb(), parse_mode='Markdown')
        context.user_data['state'] = None

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    if state == 'redeem':
        key = update.message.text.strip()
        check = await db.query("SELECT * FROM prime_passes WHERE pass_key=? AND is_used=0", (key,), fetchone=True)
        if check:
            await db.query("UPDATE prime_passes SET is_used=1, used_by=? WHERE pass_key=?", (update.effective_user.id, key), commit=True)
            await db.query("UPDATE users SET account_type='premium' WHERE user_id=?", (update.effective_user.id,), commit=True)
            await update.message.reply_text("⭐ *Premium Activated Successfully!*")
        else:
            await update.message.reply_text("❌ Invalid or used key.")
        context.user_data['state'] = None

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        txt, kb = UI.admin_panel()
        await update.message.reply_text(txt, reply_markup=kb, parse_mode='Markdown')

async def post_init(application):
    await db.connect()
    print("Database Connected and Bot Initialized.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_files))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
