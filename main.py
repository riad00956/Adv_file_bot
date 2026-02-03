import logging
import asyncio
from telegram import Update, constants
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
# Paste your credentials here directly
BOT_TOKEN = "8255821774:AAEOmf1OLvLcZb4NmHHdaGzwROx19q2P9yU"
ADMIN_ID = 7832264582  # Replace with your numeric Telegram ID
FS_CHANNEL = "@rifatsbotz" # Replace with your channel (with @)
# =================================================

# Enable Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

async def is_maint():
    """Check if Maintenance Mode is active."""
    res = await db.query("SELECT value FROM settings WHERE key='maintenance'", fetchone=True)
    return res['value'] == "1" if res else False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # 1. Register User
    await db.query(
        "INSERT OR IGNORE INTO users (user_id, first_name, username, join_date) VALUES (?,?,?,?)", 
        (user.id, user.first_name, user.username, utils.datetime.now().isoformat()), 
        commit=True
    )
    
    # 2. Check Maintenance (Admin bypasses)
    if await is_maint() and user.id != ADMIN_ID:
        return await update.message.reply_text("🚧 *Bot is currently under maintenance.*\nPlease try again later.", parse_mode='Markdown')

    # 3. Handle File Deep Link (e.g., /start file_123)
    if context.args:
        # Check Force Join first for file access
        if not await utils.force_join(context.bot, user.id, FS_CHANNEL):
            return await update.message.reply_text(
                f"❌ *Access Denied!*\n\nYou must join {FS_CHANNEL} to download files from this bot.",
                parse_mode='Markdown'
            )

        file = await db.query("SELECT * FROM files WHERE file_code=?", (context.args[0],), fetchone=True)
        if file:
            await db.query("UPDATE files SET views = views + 1 WHERE id=?", (file['id'],), commit=True)
            caption = f"📁 *File:* `{file['file_name']}`\n⚖️ *Size:* {utils.format_size(file['file_size'])}\n👁 *Views:* {file['views']+1}"
            
            try:
                if file['file_type'] == 'photo':
                    await update.message.reply_photo(file['file_id'], caption=caption, parse_mode='Markdown')
                elif file['file_type'] == 'video':
                    await update.message.reply_video(file['file_id'], caption=caption, parse_mode='Markdown')
                else:
                    await update.message.reply_document(file['file_id'], caption=caption, parse_mode='Markdown')
                return
            except Exception as e:
                return await update.message.reply_text("❌ *Error:* File might have been deleted from Telegram servers.")

    # 4. Standard Start Menu
    u_data = await db.query("SELECT account_type FROM users WHERE user_id=?", (user.id,), fetchone=True)
    acc_type = u_data['account_type'] if u_data else 'free'
    txt, kb = UI.main_menu(acc_type)
    await update.message.reply_text(txt, reply_markup=kb, parse_mode='Markdown')

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    # Maintenance Check
    if await is_maint() and user_id != ADMIN_ID:
        return await query.edit_message_text("🚧 Maintenance mode is ON.")

    if data == "nav_start":
        u_data = await db.query("SELECT account_type FROM users WHERE user_id=?", (user_id,), fetchone=True)
        txt, kb = UI.main_menu(u_data['account_type'])
        await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    elif data == "nav_upload":
        await query.edit_message_text(
            "📤 *Ready to Upload*\n\nSend me any Document, Video, or Photo now.\n\n_Note: Max file size is 2GB._", 
            reply_markup=UI.back_kb(), 
            parse_mode='Markdown'
        )
        context.user_data['state'] = 'upload'

    elif data.startswith("nav_myfiles_"):
        page = int(data.split("_")[2])
        files = await db.query(
            "SELECT * FROM files WHERE owner_id=? ORDER BY id DESC LIMIT 10 OFFSET ?", 
            (user_id, page*10), 
            fetchall=True
        )
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
        await query.edit_message_text(
            "⭐ *Prime Pass Redemption*\n\nPlease type and send your *Prime Pass Key* below:", 
            reply_markup=UI.back_kb(), 
            parse_mode='Markdown'
        )
        context.user_data['state'] = 'redeem'

    elif data.startswith("del_"):
        f_id = data.split("_")[1]
        await db.query("DELETE FROM files WHERE id=? AND owner_id=?", (f_id, user_id), commit=True)
        await query.answer("🗑 File Deleted Successfully", show_alert=True)
        # Refresh the list
        files = await db.query("SELECT * FROM files WHERE owner_id=? ORDER BY id DESC LIMIT 10 OFFSET 0", (user_id,), fetchall=True)
        total = (await db.query("SELECT COUNT(*) as count FROM files WHERE owner_id=?", (user_id,), fetchone=True))['count']
        txt, kb = UI.my_files_list(files, 0, total)
        await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    # --- Admin Handlers ---
    elif data == "adm_stats" and user_id == ADMIN_ID:
        u_count = (await db.query("SELECT COUNT(*) as c FROM users", fetchone=True))['c']
        f_count = (await db.query("SELECT COUNT(*) as c FROM files", fetchone=True))['c']
        await query.answer(f"📊 Stats\nUsers: {u_count}\nFiles: {f_count}", show_alert=True)
    
    elif data == "adm_gen" and user_id == ADMIN_ID:
        key = utils.gen_prime_key()
        await db.query("INSERT INTO prime_passes (pass_key) VALUES (?)", (key,), commit=True)
        await query.edit_message_text(f"✅ *New Prime Pass Generated:*\n\n`{key}`\n\nShare this with the user.", reply_markup=UI.admin_panel(), parse_mode='Markdown')

    elif data == "adm_maint" and user_id == ADMIN_ID:
        curr = await is_maint()
        new_val = "0" if curr else "1"
        await db.query("UPDATE settings SET value=? WHERE key='maintenance'", (new_val,), commit=True)
        await query.answer(f"Maintenance Mode: {'OFF' if curr else 'ON'}", show_alert=True)

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get('state') != 'upload':
        return # Ignore files sent without clicking upload button

    msg = update.message
    file_obj = msg.document or msg.video or (msg.photo[-1] if msg.photo else None)
    
    if not file_obj:
        return

    f_id = file_obj.file_id
    f_name = getattr(file_obj, 'file_name', f"File_{utils.gen_code(4)}")
    f_size = getattr(file_obj, 'file_size', 0)
    f_type = 'photo' if msg.photo else ('video' if msg.video else 'document')
    f_code = utils.gen_code()
    
    # Save to Database
    await db.query(
        "INSERT INTO files (file_id, file_type, file_name, file_size, file_code, owner_id, upload_date, expiry_date) VALUES (?,?,?,?,?,?,?,?)",
        (f_id, f_type, f_name, f_size, f_code, user_id, utils.datetime.now().isoformat(), utils.get_expiry()), 
        commit=True
    )
    
    # Cleanup UI
    await msg.delete()
    link = f"https://t.me/{context.bot.username}?start={f_code}"
    await context.bot.send_message(
        user_id, 
        f"✅ *File Uploaded Successfully!*\n\n🔗 *Link:* `{link}`", 
        reply_markup=UI.back_kb(), 
        parse_mode='Markdown'
    )
    context.user_data['state'] = None

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = context.user_data.get('state')

    if state == 'redeem':
        key = update.message.text.strip()
        check = await db.query("SELECT * FROM prime_passes WHERE pass_key=? AND is_used=0", (key,), fetchone=True)
        
        await update.message.delete()
        if check:
            await db.query("UPDATE prime_passes SET is_used=1, used_by=? WHERE pass_key=?", (user_id, key), commit=True)
            await db.query("UPDATE users SET account_type='premium' WHERE user_id=?", (user_id,), commit=True)
            await context.bot.send_message(user_id, "⭐ *Congratulations!*\nYour account has been upgraded to Premium.", parse_mode='Markdown', reply_markup=UI.back_kb())
        else:
            await context.bot.send_message(user_id, "❌ *Invalid or used key.*", parse_mode='Markdown', reply_markup=UI.back_kb())
        context.user_data['state'] = None

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hidden command to access admin panel."""
    if update.effective_user.id == ADMIN_ID:
        txt, kb = UI.admin_panel()
        await update.message.reply_text(txt, reply_markup=kb, parse_mode='Markdown')

def main():
    # Initialize Database first
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.connect())
    
    # Build Application
    # .job_queue(None) is REQUIRED to fix the Python 3.13 crash on Render
    app = ApplicationBuilder().token(BOT_TOKEN).job_queue(None).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_files))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("--- Premium File Bot Started Successfully ---")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
