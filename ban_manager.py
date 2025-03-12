import json
import os
from aiogram import Router, types
from aiogram.filters import Command, BaseFilter

# ID Admin
ADMIN_ID = 1985817060  

# File danh sách bị ban
BANNED_USERS_FILE = "banned_users.json"

# Load danh sách bị ban
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Lưu danh sách bị ban
def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Tạo router
router = Router()

# Bộ lọc kiểm tra người dùng bị ban
class IsBanned(BaseFilter):
    async def __call__(self, event: types.Message | types.CallbackQuery | types.InlineQuery) -> bool:
        banned_users = load_json(BANNED_USERS_FILE)
        return str(event.from_user.id) in banned_users

# Kiểm tra và xóa nút nếu người dùng bị ban
async def remove_buttons(message: types.Message):
    try:
        await message.edit_reply_markup(reply_markup=None)  # Xóa nút
    except:
        pass  # Nếu không thể xóa thì bỏ qua lỗi

# Chặn tin nhắn & xóa nút
@router.message(IsBanned())
async def check_banned_users(message: types.Message):
    await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.")
    await remove_buttons(message)

# Chặn nút bấm & xóa luôn nút
@router.callback_query(IsBanned())
async def check_banned_callbacks(callback: types.CallbackQuery):
    await callback.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin.", show_alert=True)
    await remove_buttons(callback.message)

# Chặn inline query
@router.inline_query(IsBanned())
async def check_banned_inline(inline_query: types.InlineQuery):
    await inline_query.answer([], cache_time=1, switch_pm_text="🚫 Bạn đã bị khóa.", switch_pm_parameter="banned")

# Lệnh ban người dùng
@router.message(Command("ban"))
async def ban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
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

    await message.answer(f"✅ Đã khóa tài khoản {user_id}, họ sẽ không thể sử dụng nút hoặc gửi tin nhắn.")

# Lệnh mở khóa người dùng
@router.message(Command("unban"))
async def unban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
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

# Lệnh kiểm tra danh sách bị ban
@router.message(Command("banned_list"))
async def banned_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    banned_users = load_json(BANNED_USERS_FILE)
    if not banned_users:
        await message.answer("✅ Hiện không có ai bị ban.")
    else:
        banned_list_text = "🚫 Danh sách người dùng bị ban:\n" + "\n".join(banned_users.keys())
        await message.answer(banned_list_text)
