import os
import json
from aiogram import Router, types, F
from aiogram.filters import Command

# ID của admin
ADMIN_ID = "1985817060"

# File lưu danh sách bị ban
BANNED_USERS_FILE = "banned_users.json"
BALANCE_FILE = "user_data.json"  # File chứa số dư của người chơi

# Load dữ liệu từ file JSON
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Lưu dữ liệu vào file JSON
def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Danh sách người bị ban
banned_users = load_json(BANNED_USERS_FILE)
user_data = load_json(BALANCE_FILE)

# Tạo router
router = Router()

# Kiểm tra xem người dùng có bị ban không
def is_banned(user_id):
    return str(user_id) in banned_users

# Chặn tin nhắn của người bị ban
@router.message(F.from_user.id.func(is_banned))
async def check_banned_users(message: types.Message):
    await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.\nVui lòng nhắn tin @hoanganh11829 để biết lý do.")
    return

# Chặn luôn cả khi bấm nút (callback query)
@router.callback_query(F.from_user.id.func(is_banned))
async def block_banned_callbacks(callback: types.CallbackQuery):
    await callback.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.", show_alert=True)

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

    # Thêm vào danh sách bị ban
    banned_users[user_id] = True
    save_json(BANNED_USERS_FILE, banned_users)

    # Trừ hết số dư của người dùng
    if user_id in user_data.get("balances", {}):
        user_data["balances"][user_id] = 0
        save_json(BALANCE_FILE, user_data)

    await message.answer(f"✅ Đã khóa tài khoản {user_id} và trừ hết số dư.")

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
