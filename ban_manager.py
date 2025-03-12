import json
import os
from aiogram import Router, types, BaseMiddleware
from aiogram.filters import Command, Filter
from typing import Any, Awaitable, Callable, Dict, Union

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

# Middleware kiểm tra người dùng bị ban
class BanMiddleware(BaseMiddleware):
    async def __call__(
        self, handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]], event: types.TelegramObject, data: Dict[str, Any]
    ) -> Any:
        banned_users = load_json(BANNED_USERS_FILE)
        user_id = str(getattr(event, "from_user", {}).get("id", ""))
        if user_id in banned_users:
            if isinstance(event, types.Message):
                await event.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.")
            elif isinstance(event, types.CallbackQuery):
                await event.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.", show_alert=True)
            return
        return await handler(event, data)

router.message.middleware(BanMiddleware())
router.callback_query.middleware(BanMiddleware())
router.inline_query.middleware(BanMiddleware())

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
