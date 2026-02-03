from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class UI:
    @staticmethod
    def main_menu(acc_type):
        status = "⭐ Premium" if acc_type == 'premium' else "🆓 Free"
        text = (
            "👋 *Welcome to File Store Bot*\n\n"
            f"👤 *Account Type:* {status}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "নিচের বাটনগুলো ব্যবহার করে বটটি কন্ট্রোল করুন।"
        )
        kb = [
            [InlineKeyboardButton("📤 Upload File", callback_data="nav_upload")],
            [InlineKeyboardButton("📁 My Files", callback_data="nav_myfiles_0")],
            [InlineKeyboardButton("💳 Get Premium", callback_data="nav_premium")]
        ]
        return text, InlineKeyboardMarkup(kb)

    @staticmethod
    def back_kb():
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="nav_start")]])

    @staticmethod
    def my_files_list(files, page, total):
        text = "📂 *Your Uploaded Files:*\n"
        kb = []
        if not files:
            text += "_No files found._"
        else:
            for f in files:
                text += f"\n• `{f['file_name']}`"
                kb.append([InlineKeyboardButton(f"📄 {f['file_name'][:20]}", callback_data=f"view_{f['id']}")])
        
        # Pagination
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"nav_myfiles_{page-1}"))
        if (page + 1) * 10 < total: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"nav_myfiles_{page+1}"))
        if nav: kb.append(nav)
        
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="nav_start")])
        return text, InlineKeyboardMarkup(kb)

    @staticmethod
    def file_view(file, bot_username):
        link = f"https://t.me/{bot_username}?start={file['file_code']}"
        text = (
            f"📄 *File Name:* `{file['file_name']}`\n"
            f"⚖️ *Size:* {file['file_size']}\n"
            f"👁️ *Views:* {file['views']}\n"
            f"📅 *Upload Date:* {file['upload_date'][:10]}\n\n"
            f"🔗 *Short Link:* `{link}`"
        )
        kb = [
            [InlineKeyboardButton("🗑️ Delete File", callback_data=f"del_{file['id']}")],
            [InlineKeyboardButton("🔙 Back", callback_data="nav_myfiles_0")]
        ]
        return text, InlineKeyboardMarkup(kb)

    @staticmethod
    def admin_panel():
        text = "⚙️ *Admin Control Panel*"
        kb = [
            [InlineKeyboardButton("📊 Stats", callback_data="adm_stats")],
            [InlineKeyboardButton("🔑 Gen Prime Key", callback_data="adm_gen")],
            [InlineKeyboardButton("🔙 Close", callback_data="nav_start")]
        ]
        return text, InlineKeyboardMarkup(kb)
