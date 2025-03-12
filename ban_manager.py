import os
import json
import logging
import pytz
from datetime import datetime
from aiogram import Router, types, Bot
from aiogram.filters import Command, Filter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ID của admin (lưu dưới dạng chuỗi)
ADMIN_ID = "1985817060"

# File lưu trữ danh sách người bị ban và số dư người dùng
BANNED_USERS_FILE = "banned_users.json"
BALANCE_FILE = "user_data.json"

# Hàm tải dữ liệu JSON từ file
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Hàm lưu dữ liệu vào file JSON
def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Load danh sách người bị ban từ file
banned_users = load_json(BANNED_USERS_FILE)

# Khởi tạo router
router = Router()

# Lớp Filter để kiểm tra người dùng bị ban (áp dụng cho cả message và callback)
class IsBanned(Filter):
    async def __call__(self, event: types.Message | types.CallbackQuery) -> bool:
        return str(event.from_user.id) in banned_users

# Chặn tin nhắn của người dùng bị ban
@router.message(IsBanned())
async def banned_message_handler(message: types.Message):
    await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.\nVui lòng nhắn tin admin @hoanganh11829 để biết lý do.")

# Chặn callback của người dùng bị ban
@router.callback_query(IsBanned())
async def banned_callback_handler(callback: types.CallbackQuery):
    await callback.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.", show_alert=True)

# Lệnh /ban của admin
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

    # Trừ hết số dư của người dùng bị ban trong file BALANCE_FILE
    balance_data = load_json(BALANCE_FILE)
    if "balances" in balance_data and user_id in balance_data["balances"]:
        balance_data["balances"][user_id] = 0
        save_json(BALANCE_FILE, balance_data)

    await message.answer(f"✅ Đã khóa tài khoản {user_id} và trừ hết số dư.")

# Lệnh /unban của admin
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

# Nếu cần, bạn có thể import router này trong file chính của bot bằng:
# from ban_manager import router as ban_router
# dp.include_router(ban_router)

# Cấu hình logging nếu cần
logging.basicConfig(level=logging.INFO)
