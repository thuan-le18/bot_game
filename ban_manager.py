from aiogram import Router, types
from aiogram.filters import Command, BaseFilter
import json
import os

# ID của admin
ADMIN_ID = "1985817060"

# File lưu danh sách bị ban
BANNED_USERS_FILE = "banned_users.json"

# Hàm load dữ liệu từ JSON
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Hàm lưu dữ liệu vào JSON
def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Danh sách người bị ban
banned_users = load_json(BANNED_USERS_FILE)

# Tạo router
router = Router()

# Bộ lọc kiểm tra người dùng bị ban
class IsBanned(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return str(message.from_user.id) in banned_users

# Middleware chặn người dùng bị ban
@router.message(IsBanned())
async def check_banned_users(message: types.Message):
    await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.")
    return  # Chặn xử lý tiếp theo

# Lệnh ban người dùng
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
    if user_id in banned_users:
        await message.answer(f"⚠️ Người dùng {user_id} đã bị khóa trước đó.")
        return
    
    banned_users[user_id] = True
    save_json(BANNED_USERS_FILE, banned_users)
    await message.answer(f"✅ Đã khóa tài khoản {user_id}.")

# Lệnh mở khóa người dùng
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
        await message.answer("⚠️ Người dùng này không bị khóa.")

