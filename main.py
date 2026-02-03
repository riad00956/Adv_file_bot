import logging, asyncio
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from database import db
from ui import UI
import utils

# ================= CONFIGURATION =================
BOT_TOKEN = "8255821774:AAEOmf1OLvLcZb4NmHHdaGzwROx19q2P9yU"
ADMIN_ID = 7832264582  # Your Telegram ID
FS_CHANNEL = "@rifatsbotz" # Channel username for force join
# =================================================

async def is_maint():
    res = await db.query("SELECT value FROM settings WHERE key='maintenance'", fetchone=True)
    return res['value'] == "1"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.query("INSERT OR IGNORE INTO users (user_id, first_name, username, join_date) VALUES (?,?,?,?)", 
                  (user.id, user.first_name, user.username, utils.datetime.now().isoformat()), commit=True)
    
    # Check Maintenance
    if await is_maint() and user.id != ADMIN_ID:
        return await update.message.reply_text("🚧 *Bot is under maintenance.*")

    # Check Force Join
    if not await utils.force_join(context.bot, user.id, FS_CHANNEL):
        return await update.message.reply_text(f"❌ *Access Denied!*\n\nYou must join {FS_CHANNEL} to use this bot.")

    # Deep Link Handler
    if context.args:
        file = await db.query("SELECT * FROM files WHERE file_code=?", (context.args[0],), fetchone=True)
        if file:
            await db.query("UPDATE files SET views = views + 1 WHERE id=?", (file['id'],), commit=True)
            caption = f"📁 *File:* `{file['file_name']}`\n⚖️ *Size:* {utils.format_size(file['file_size'])}"
            if file['file_type'] == 'photo': await update.message.reply_photo(file['file_id'], caption=caption, parse_mode='Markdown')
            elif file['file_type'] == 'video': await update.message.reply_video(file['file_id'], caption=caption, parse_mode='Markdown')
            else: await update.message.reply_document(file['file_id'], caption=caption, parse_mode='Markdown')
            return

    u_data = await db.query("SELECT account_type FROM users WHERE user_id=?", (user.id,), fetchone=True)
    txt, kb = UI.main_menu(u_data['account_type'])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode='Markdown')

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == "nav_start":
        u_data = await db.query("SELECT account_type FROM users WHERE user_id=?", (user_id,), fetchone=True)
        txt, kb = UI.main_menu(u_data['account_type'])
        await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    elif data == "nav_upload":
        await query.edit_message_text("📤 *Send me any File, Photo, or Video.*", reply_markup=UI.back_kb(), parse_mode='Markdown')
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
        txt, kb = UI.file_view(file, context.bot.username)
        await query.edit_message_text(txt, reply_markup=kb, parse_mode='Markdown')

    elif data == "nav_premium":
        await query.edit_message_text("⭐ *Premium Upgrade*\n\nEnter your Prime Pass Key below to upgrade.", reply_markup=UI.back_kb(), parse_mode='Markdown')
        context.user_data['state'] = 'redeem'

    # Admin Logic
    elif data == "adm_stats" and user_id == ADMIN_ID:
        u_count = (await db.query("SELECT COUNT(*) as c FROM users", fetchone=True))['c']
        f_count = (await db.query("SELECT COUNT(*) as c FROM files", fetchone=True))['c']
        await query.answer(f"Users: {u_count} | Files: {f_count}", show_alert=True)
    
    elif data == "adm_gen" and user_id == ADMIN_ID:
        key = utils.gen_prime_key()
        await db.query("INSERT INTO prime_passes (pass_key) VALUES (?)", (key,), commit=True)
        await query.edit_message_text(f"✅ *Generated Prime Pass:*\n`{key}`", reply_markup=UI.admin_panel(), parse_mode='Markdown')

    elif data == "adm_maint" and user_id == ADMIN_ID:
        curr = await is_maint()
        new_val = "0" if curr else "1"
        await db.query("UPDATE settings SET value=? WHERE key='maintenance'", (new_val,), commit=True)
        await query.answer(f"Maintenance: {'OFF' if curr else 'ON'}")

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get('state') != 'upload': return
    
    msg = update.message
    file_obj = msg.document or msg.video or (msg.photo[-1] if msg.photo else None)
    if not file_obj: return

    f_id = file_obj.file_id
    f_name = getattr(file_obj, 'file_name', f"File_{utils.gen_code(4)}")
    f_size = getattr(file_obj, 'file_size', 0)
    f_type = 'photo' if msg.photo else ('video' if msg.video else 'document')
    f_code = utils.gen_code()
    
    await db.query("INSERT INTO files (file_id, file_type, file_name, file_size, file_code, owner_id, upload_date, expiry_date) VALUES (?,?,?,?,?,?,?,?)",
                  (f_id, f_type, f_name, f_size, f_code, user_id, utils.datetime.now().isoformat(), utils.get_expiry()), commit=True)
    
    await msg.delete()
    link = f"https://t.me/{context.bot.username}?start={f_code}"
    await context.bot.send_message(user_id, f"✅ *Uploaded!*\n\n`{link}`", reply_markup=UI.back_kb(), parse_mode='Markdown')
    context.user_data['state'] = None

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = context.user_data.get('state')

    if state == 'redeem':
        key = update.message.text.strip()
        check = await db.query("SELECT * FROM prime_passes WHERE pass_key=? AND is_used=0", (key,), fetchone=True)
        if check:
            await db.query("UPDATE prime_passes SET is_used=1, used_by=? WHERE pass_key=?", (user_id, key), commit=True)
            await db.query("UPDATE users SET account_type='premium' WHERE user_id=?", (user_id,), commit=True)
            await update.message.reply_text("⭐ *Account Upgraded to Premium!*")
        else:
            await update.message.reply_text("❌ Invalid or Expired Key.")
        context.user_data['state'] = None

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        txt, kb = UI.admin_panel()
        await update.message.reply_text(txt, reply_markup=kb, parse_mode='Markdown')

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.connect())
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_files))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is alive...")
    app.run_polling()
