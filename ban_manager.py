import json
import os
from aiogram import Router, types
from aiogram.filters import Command, Filter

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

# Danh sách người bị ban
banned_users = load_json(BANNED_USERS_FILE)

# Tạo router
router = Router()

# Lớp kiểm tra người dùng bị ban
class IsBanned(Filter):
    async def __call__(self, event: types.Message | types.CallbackQuery | types.InlineQuery) -> bool:
        return str(event.from_user.id) in banned_users

# Chặn tất cả các lệnh từ người dùng bị ban
@router.message(IsBanned())
async def handle_banned_users(message: types.Message):
    await message.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin. Bạn không thể sử dụng bot này.")
    return

# Chặn tất cả các nút bấm từ người dùng bị ban
@router.callback_query(IsBanned())
async def handle_banned_callbacks(callback: types.CallbackQuery):
    await callback.answer("🚫 Tài khoản của bạn đã bị khóa bởi admin. Bạn không thể sử dụng nút bấm.", show_alert=True)

# Lệnh ban người dùng
@router.message(Command("ban"))
async def ban_user(message: types.Message):
    # Kiểm tra quyền admin
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    # Kiểm tra định dạng lệnh
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("❌ Sử dụng: /ban <user_id>")
        return
    
    user_id = args[1]
    
    # Kiểm tra xem người dùng đã bị ban chưa
    if user_id in banned_users:
        await message.answer(f"❌ Tài khoản {user_id} đã bị khóa từ trước.")
        return
    
    # Thêm người dùng vào danh sách bị ban
    banned_users[user_id] = True
    save_json(BANNED_USERS_FILE, banned_users)
    
    # Thông báo thành công
    await message.answer(f"✅ Đã khóa tài khoản {user_id}. Người này sẽ không thể sử dụng bot hoặc nút bấm.")

# Lệnh mở khóa người dùng
@router.message(Command("unban"))
async def unban_user(message: types.Message):
    # Kiểm tra quyền admin
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    # Kiểm tra định dạng lệnh
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("❌ Sử dụng: /unban <user_id>")
        return
    
    user_id = args[1]
    
    # Kiểm tra xem người dùng có bị ban không
    if user_id in banned_users:
        del banned_users[user_id]
        save_json(BANNED_USERS_FILE, banned_users)
        await message.answer(f"✅ Đã mở khóa tài khoản {user_id}.")
    else:
        await message.answer(f"❌ Tài khoản {user_id} không bị khóa.")

# Lệnh hiển thị danh sách người bị ban
@router.message(Command("show_banned"))
async def show_banned_users(message: types.Message):
    # Kiểm tra quyền admin
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    if not banned_users:
        await message.answer("📂 Danh sách người bị ban hiện đang trống.")
    else:
        banned_list = "\n".join(banned_users.keys())
        await message.answer(f"📜 Danh sách người bị ban:\n{banned_list}")

# Lệnh kiểm tra xem một người dùng có bị ban không
@router.message(Command("check_ban"))
async def check_ban(message: types.Message):
    # Kiểm tra quyền admin
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    
    # Kiểm tra định dạng lệnh
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        await message.answer("❌ Sử dụng: /check_ban <user_id>")
        return
    
    user_id = args[1]
    
    # Kiểm tra xem người dùng có bị ban không
    if user_id in banned_users:
        await message.answer(f"✅ Tài khoản {user_id} đã bị khóa.")
    else:
        await message.answer(f"❌ Tài khoản {user_id} không bị khóa.")
