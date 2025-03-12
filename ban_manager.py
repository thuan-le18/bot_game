from aiogram import Router, types
from aiogram.filters import Command, BaseFilter
import json
import os

# ID của admin
ADMIN_ID = "1985817060"

# File lưu danh sách bị ban
BANNED_USERS_FILE = "banned_users.json"

# Load danh sách bị ban từ file
def load_json(filename):
    if os.path.exists(BANNED_USERS_FILE):
        with open(BANNED_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Lưu danh sách bị ban vào file
def save_json(filename, data):
    with open(BANNED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Danh sách người bị ban
banned_users = load_json(BANNED_USERS_FILE)

# Tạo router
router = Router()

# Middleware kiểm tra user có bị ban không
class IsBanned(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        user_id = str(message.from_user.id)
        if user_id in banned_users:
            try:
                await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.")
            except:
                pass  # Nếu bot không gửi được tin nhắn, bỏ qua lỗi
            return True
        return False

# 🔥 Chặn tất cả tin nhắn từ người bị ban
@router.message(IsBanned())
async def blocked_user_message(message: types.Message):
    return  # Không xử lý gì thêm nếu user bị ban

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
        await message.answer("❌ Tài khoản này không bị khóa.")
