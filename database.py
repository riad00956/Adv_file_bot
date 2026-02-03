import aiosqlite
from datetime import datetime

class Database:
    def __init__(self, db_path="bot_database.db"):
        self.db_path = db_path

    async def connect(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, 
                join_date TEXT, account_type TEXT DEFAULT 'free', is_banned INTEGER DEFAULT 0)""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, file_type TEXT, 
                file_name TEXT, file_size INTEGER, file_code TEXT UNIQUE, 
                owner_id INTEGER, upload_date TEXT, expiry_date TEXT, views INTEGER DEFAULT 0)""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS prime_passes (
                pass_key TEXT PRIMARY KEY, is_used INTEGER DEFAULT 0, used_by INTEGER)""")
            
            await db.execute("""CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT)""")
            
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', '0')")
            await db.commit()

    async def query(self, sql, params=(), fetchone=False, fetchall=False, commit=False):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            if commit: await db.commit()
            if fetchone: return await cursor.fetchone()
            if fetchall: return await cursor.fetchall()
            return cursor

db = Database()
