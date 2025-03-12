import json
import os
from aiogram import Router, types
from aiogram.filters import Command, BaseFilter

# ID của admin
ADMIN_ID = "1985817060"

# File lưu danh sách bị ban
BANNED_USERS_FILE = "banned_users.json"

# Load danh sách bị ban từ file
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Lưu danh sách bị ban vào file
def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Tạo router
router = Router()

# Lớp kiểm tra người dùng bị ban
class IsBanned(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        banned_users = load_json(BANNED_USERS_FILE)
        return str(message.from_user.id) in banned_users

# Kiểm tra và chặn người bị ban trước khi họ có thể làm gì
@router.message(IsBanned())
async def check_banned_users(message: types.Message):
    await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.")

@router.callback_query(IsBanned())
async def check_banned_callbacks(callback: types.CallbackQuery):
    await callback.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.", show_alert=True)

@router.inline_query(IsBanned())
async def check_banned_inline(inline_query: types.InlineQuery):
    await inline_query.answer([], cache_time=1, switch_pm_text="🚫 Bạn đã bị khóa.", switch_pm_parameter="banned")

@router.edited_message(IsBanned())
async def check_banned_edited_message(message: types.Message):
    await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.")

@router.chat_member(IsBanned())
async def check_banned_chat_member(update: types.ChatMemberUpdated):
    pass

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
    banned_users = load_json(BANNED_USERS_FILE)
    banned_users[user_id] = True
    save_json(BANNED_USERS_FILE, banned_users)
    
    await message.answer(f"✅ Đã khóa tài khoản {user_id}, người này sẽ không thể sử dụng bot.")

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
    banned_users = load_json(BANNED_USERS_FILE)
    if user_id in banned_users:
        del banned_users[user_id]
        save_json(BANNED_USERS_FILE, banned_users)
        await message.answer(f"✅ Đã mở khóa tài khoản {user_id}.")
    else:
        await message.answer("❌ Tài khoản này không bị khóa.")

# Xuất các thành phần cần import
__all__ = ["IsBanned", "router"]
