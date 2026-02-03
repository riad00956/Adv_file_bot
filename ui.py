from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class UI:
    @staticmethod
    def main_menu(user_type):
        badge = "⭐ Premium" if user_type == 'premium' else "🆓 Free Member"
        text = f"📁 *Premium File Sharing Bot*\n\nStatus: `{badge}`\n\nSelect an option below:"
        kb = [
            [InlineKeyboardButton("📤 Upload File", callback_data="nav_upload"),
             InlineKeyboardButton("📂 My Files", callback_data="nav_myfiles_0")],
            [InlineKeyboardButton("👤 My Profile", callback_data="nav_profile"),
             InlineKeyboardButton("⭐ Prime Pass", callback_data="nav_premium")],
            [InlineKeyboardButton("ℹ Help & Info", callback_data="nav_help")]
        ]
        return text, InlineKeyboardMarkup(kb)

    @staticmethod
    def file_view(file, bot_username):
        link = f"https://t.me/{bot_username}?start={file['file_code']}"
        text = (f"📄 *File Name:* `{file['file_name']}`\n"
                f"⚖️ *Size:* {file['file_size']}\n"
                f"👁 *Views:* {file['views']}\n"
                f"⏳ *Expiry:* {file['expiry_date'].split('T')[0]}\n\n"
                f"🔗 *Share Link:* `{link}`")
        kb = [
            [InlineKeyboardButton("🔗 Copy Link", url=link)],
            [InlineKeyboardButton("🗑 Delete File", callback_data=f"del_{file['id']}"),
             InlineKeyboardButton("⏳ Set Expiry", callback_data=f"exp_{file['id']}")],
            [InlineKeyboardButton("🔙 Back to List", callback_data="nav_myfiles_0")]
        ]
        return text, InlineKeyboardMarkup(kb)

    @staticmethod
    def my_files_list(files, page, total):
        kb = []
        for f in files:
            kb.append([InlineKeyboardButton(f"📄 {f['file_name'][:25]}", callback_data=f"view_{f['id']}")])
        
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"nav_myfiles_{page-1}"))
        if (page + 1) * 10 < total: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"nav_myfiles_{page+1}"))
        if nav: kb.append(nav)
        kb.append([InlineKeyboardButton("🔙 Main Menu", callback_data="nav_start")])
        return "📂 *Your Uploaded Files:*", InlineKeyboardMarkup(kb)

    @staticmethod
    def admin_panel():
        kb = [
            [InlineKeyboardButton("📊 Bot Stats", callback_data="adm_stats"),
             InlineKeyboardButton("📢 Broadcast", callback_data="adm_bc")],
            [InlineKeyboardButton("⭐ Generate Pass", callback_data="adm_gen")],
            [InlineKeyboardButton("🚧 Toggle Maintenance", callback_data="adm_maint")],
            [InlineKeyboardButton("❌ Close", callback_data="nav_start")]
        ]
        return "🔐 *Admin Control Center*", InlineKeyboardMarkup(kb)

    @staticmethod
    def back_kb():
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="nav_start")]])
