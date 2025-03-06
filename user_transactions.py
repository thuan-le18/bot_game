from aiogram import Router, types
from aiogram.filters import Text
from database import deposit_history, withdrawal_history

router = Router()

@router.message(F.text.startswith("📜 Lịch sử giao dịch"))
async def user_transaction_history(message: types.Message):
    user_id = message.from_user.id

    # Lọc lịch sử của user
    user_deposits = [d for d in deposit_history if d.startswith(f"User {user_id}")]
    user_withdrawals = [w for w in withdrawal_history if w.startswith(f"User {user_id}")]

    if not user_deposits and not user_withdrawals:
        await message.answer("📌 Bạn chưa có lịch sử nạp hoặc rút tiền.")
    else:
        deposit_text = "\n📥 Nạp tiền:\n" + "\n".join(user_deposits) if user_deposits else "Không có giao dịch nạp."
        withdraw_text = "\n📤 Rút tiền:\n" + "\n".join(user_withdrawals) if user_withdrawals else "Không có giao dịch rút."
        await message.answer(deposit_text + "\n" + withdraw_text)
