import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

from database import db
from ui import UI
import utils

BOT_TOKEN = "8255821774:AAEOmf1OLvLcZb4NmHHdaGzwROx19q2P9yU"
ADMIN_ID = 7832264582
FS_CHANNEL = "@rifatsbotz"

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return

    # User Registration
    await db.query(
        "INSERT OR IGNORE INTO users (user_id, first_name, username, join_date) VALUES (?,?,?,?)", 
        (user.id, user.first_name, user.username, datetime.now().isoformat()), 
        commit=True
    )

    # Force Join & Deep Link
    if context.args:
        if not await utils.force_join(context.bot, user.id, FS_CHANNEL):
            await update.message.reply_text(f"⚠️ *Access Denied!*\nPlease join {FS_CHANNEL} to get the file.", parse_mode='Markdown')
            return

        file = await db.query("SELECT * FROM files WHERE file_code=?", (context.args[0],), fetchone=True)
        if file:
            await db.query("UPDATE files SET views = views + 1 WHERE id=?", (file['id'],), commit=True)
            cap = f"📁 *File:* `{file['file_name']}`\n⚖️ *Size:* {utils.format_size(file['file_size'])}"
            if file['file_type'] == 'photo': await update.message.reply_photo(file['file_id'], caption=cap, parse_mode='Markdown')
            elif file['file_type'] == 'video': await update.message.reply_video(file['file_id'], caption=cap, parse_mode='Markdown')
            else: await update.message.reply_document(file['file_id'], caption=cap, parse_mode='Markdown')
            return

    u_data = await db.query("SELECT account_type FROM users WHERE user_id=?", (user.id,), fetchone=True)
    txt, kb = UI.main_menu(u_data['account_type'] if u_data else 'free')
    await update.message.reply_text(txt, reply_markup=kb, parse_mode='Markdown')

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != 'upload': return
    
    msg = update.message
    file_obj = msg.document or msg.video or (msg.photo[-1] if msg.photo else None)
    
    if file_obj:
        f_code = utils.gen_code()
        f_name = getattr(file_obj, 'file_name', f"File_{f_code}")
        f_type = 'photo' if msg.photo else ('video' if msg.video else 'document')
        
        await db.query(
            "INSERT INTO files (file_id, file_type, file_name, file_size, file_code, owner_id, upload_date) VALUES (?,?,?,?,?,?,?)",
            (file_obj.file_id, f_type, f_name, getattr(file_obj, 'file_size', 0), f_code, msg.from_user.id, datetime.now().isoformat()), 
            commit=True
        )
        
        link = f"https://t.me/{context.bot.username}?start={f_code}"
        await msg.reply_text(f"✅ *File Uploaded!*\n\n🔗 *Link:* `{link}`", reply_markup=UI.back_kb(), parse_mode='Markdown')
        context.user_data['state'] = None

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # DB কানেকশন মেইন থ্রেডে শুরু করা
    loop = asyncio.get_event_loop()
    loop.run_until_complete(db.connect())

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_files))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is live...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
                                                                                
