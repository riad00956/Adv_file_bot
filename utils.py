import secrets, string, random
from datetime import datetime, timedelta

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024: return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024

def gen_code(k=10):
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(k))

def gen_prime_key():
    return f"PRIME-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"

async def force_join(bot, user_id, channel):
    if not channel: return True
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_expiry(hours=24):
    return (datetime.now() + timedelta(hours=hours)).isoformat()
