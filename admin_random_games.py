from aiogram import Router, F, types
from aiogram.filters.command import CommandObject
from database import game_results  # Đảm bảo file database.py có chứa game_results

ADMIN_ID = 1985817060  # Thay bằng ID admin của bạn

router = Router()

@router.message(F.text.startswith("/chinhrandom"), CommandObject())
async def modify_random_game_result(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return  # Chỉ cho admin

    # Lấy phần argument sau lệnh
    args = command.args  # Đây là phần sau tên lệnh
    if not args:
        await message.answer("⚠️ Sai cú pháp! Dùng: /chinhrandom [game] [ID] [kết quả]")
        return

    parts = args.split()
    if len(parts) < 3:
        await message.answer("⚠️ Sai cú pháp! Dùng: /chinhrandom [game] [ID] [kết quả]")
        return

    game_name = parts[0]
    user_id = parts[1]
    result = " ".join(parts[2:]).lower()

    if game_name not in ["Jackpot", "MáyBay", "MiniPoker", "ĐàoVàng"]:
        await message.answer("⚠️ Game không tồn tại hoặc không thể chỉnh kết quả!")
        return

    # Cập nhật kết quả cho user trong game_results
    game_results[game_name][user_id] = result
    await message.answer(f"✅ Đã chỉnh kết quả {game_name} cho user {user_id}: {result}")
