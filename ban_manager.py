from aiogram import Router, types
from aiogram.filters import Command, BaseFilter
import json
import os

# ID của admin
ADMIN_ID = "1985817060"

# File lưu danh sách bị ban & số dư user
BANNED_USERS_FILE = "banned_users.json"
BALANCE_FILE = "balances.json"

# Load dữ liệu từ file
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Lưu dữ liệu vào file
def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Danh sách người bị ban & số dư
banned_users = load_json(BANNED_USERS_FILE)
balances = load_json(BALANCE_FILE)

# Tạo router
router = Router()

# Lớp kiểm tra người dùng bị ban
class IsBanned(BaseFilter):
    async def __call__(self, obj) -> bool:
        return str(obj.from_user.id) in banned_users

# **Chặn toàn bộ tin nhắn của user bị ban**
@router.message(IsBanned())
async def block_banned_users(message: types.Message):
    await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.\nVui lòng nhắn tin @hoanganh11829 để biết lý do.")
    return  # Dừng lại, không cho xử lý tiếp

# **Chặn cả callback query của user bị ban (nút bấm)**
@router.callback_query(IsBanned())
async def block_banned_callback(callback: types.CallbackQuery):
    await callback.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.\nNhắn tin @hoanganh11829 để biết lý do.", show_alert=True)
    return  # Dừng lại, không cho xử lý tiếp

# **Lệnh ban người dùng**
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
    
    # Cập nhật danh sách bị ban
    banned_users[user_id] = True
    save_json(BANNED_USERS_FILE, banned_users)

    # Trừ hết số dư user về 0
    if user_id in balances:
        balances[user_id] = 0
        save_json(BALANCE_FILE, balances)

    await message.answer(f"✅ Đã khóa tài khoản {user_id} và trừ hết số dư.")

# **Lệnh mở khóa người dùng**
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
