from aiogram import Router, types
from aiogram.filters import Text
from database import deposit_history, withdrawal_history

ADMIN_ID = 1985817060  # Thay bằng ID admin

router = Router()

@router.message(F.text.startswith"🔍 Lịch sử user")
async def check_user_transactions(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return  # Không cho user thường dùng

    try:
        user_id = message.text.split(" ")[-1]  # Lấy ID user từ lệnh admin
        user_deposits = [d for d in deposit_history if d.startswith(f"User {user_id}")]
        user_withdrawals = [w for w in withdrawal_history if w.startswith(f"User {user_id}")]

        if not user_deposits and not user_withdrawals:
            await message.answer(f"📌 User {user_id} chưa có giao dịch nạp hoặc rút tiền.")
        else:
            deposit_text = "\n📥 Nạp tiền:\n" + "\n".join(user_deposits) if user_deposits else "Không có giao dịch nạp."
            withdraw_text = "\n📤 Rút tiền:\n" + "\n".join(user_withdrawals) if user_withdrawals else "Không có giao dịch rút."
            await message.answer(f"📜 Lịch sử user {user_id}:\n{deposit_text}\n{withdraw_text}")
    except Exception:
        await message.answer("⚠️ Sai cú pháp! Dùng: 🔍 Lịch sử user [ID]")
