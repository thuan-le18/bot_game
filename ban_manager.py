from aiogram import Router, types
from aiogram.filters import Command

# ID của admin
ADMIN_ID = "1985817060"

# Danh sách người bị ban
BANNED_USERS_FILE = "banned_users.json"
banned_users = {}

# Hàm lưu danh sách vào file JSON
import json
import os

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Load danh sách banned từ file khi khởi động
banned_users = load_json(BANNED_USERS_FILE)

# Tạo router cho phần ban
router = Router()

@router.message(Command("ban"))
async def ban_user(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("❌ Sử dụng: /ban <user_id>")
        return
    
    user_id = args[1]
    banned_users[user_id] = True
    save_json(BANNED_USERS_FILE, banned_users)
    await message.answer(f"✅ Đã khóa tài khoản {user_id}.")

@router.message(Command("unban"))
async def unban_user(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("❌ Sử dụng: /unban <user_id>")
        return
    
    user_id = args[1]
    if user_id in banned_users:
        del banned_users[user_id]
        save_json(BANNED_USERS_FILE, banned_users)
        await message.answer(f"✅ Đã mở khóa tài khoản {user_id}.")
    else:
        await message.answer("❌ Tài khoản này không bị khóa.")

@router.message()
async def check_banned_users(message: types.Message):
    if str(message.from_user.id) in banned_users:
        await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.")
        return
