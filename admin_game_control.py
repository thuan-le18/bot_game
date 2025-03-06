from aiogram import Router, F, types
# from aiogram.filters import Text  # Nếu aiogram v3 thì không dùng Text, dùng F.text
from database import game_results

ADMIN_ID = 1985817060   # Thay bằng ID admin

router = Router()

@router.message(F.text.startswith("🎮 Chỉnh kết quả"))
async def modify_game_result(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return  # Không cho user thường dùng

    try:
        parts = message.text.split()
        # parts[0] = "🎮", parts[1] = "Chỉnh", parts[2] = "kết", ...
        # Nên bạn có thể cần parts[3], parts[4], parts[5], vv... Tùy cú pháp bạn muốn
        # Ở đây code gốc giả định game_name = parts[2], user_id = parts[3], result = parts[4]
        # => Lệnh admin phải có ít nhất 5 phần: ["🎮", "Chỉnh", "kết", "quả", "TàiXỉu", "12345", "thắng"]

        # Kiểm tra độ dài parts
        if len(parts) < 5:
            await message.answer("⚠️ Sai cú pháp! Dùng: 🎮 Chỉnh kết quả [game] [ID] [thắng/thua/hòa]")
            return

        game_name = parts[2]  # Tên game
        user_id = parts[3]    # ID user
        result = parts[4]     # Kết quả mong muốn (thắng/thua/hòa)

        if game_name not in ["TàiXỉu", "RồngHổ", "XócĐĩa"]:
            await message.answer("⚠️ Game không tồn tại hoặc không thể chỉnh kết quả!")
            return
        
        # Ghi kết quả
        game_results[game_name][user_id] = result
        await message.answer(f"✅ Đã chỉnh kết quả {game_name} cho user {user_id}: {result}")
    except Exception:
        await message.answer("⚠️ Sai cú pháp! Dùng: 🎮 Chỉnh kết quả [game] [ID] [thắng/thua/hòa]")
