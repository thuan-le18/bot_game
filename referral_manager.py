import os
import json
import logging
import pytz
from datetime import datetime
from aiogram import types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# File lưu trữ danh sách mời
REFERRAL_FILE = "referrals.json"

# Khởi tạo router
router = Router()

# Hàm tải danh sách từ file JSON
def load_referrals():
    if os.path.exists(REFERRAL_FILE):
        with open(REFERRAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Hàm lưu danh sách vào file JSON
def save_referrals():
    with open(REFERRAL_FILE, "w", encoding="utf-8") as f:
        json.dump(referrals, f, indent=4)

# Load dữ liệu khi bot khởi động
referrals = load_referrals()

# Hàm thêm lượt giới thiệu
def add_referral(referrer_id, new_user_id):
    if referrer_id not in referrals:
        referrals[referrer_id] = []
    referrals[referrer_id].append({"user_id": new_user_id, "timestamp": datetime.now().isoformat()})
    save_referrals()

# ===================== Hoa Hồng Handler =====================
@router.message(lambda message: message.text == "🌹 Hoa hồng")
async def referral_handler(message: types.Message):
    user_id = str(message.from_user.id)
    referral_link = f"https://t.me/@Bottx_Online_bot?start={user_id}"
    records = referrals.get(user_id, [])

    # Chuyển sang múi giờ Việt Nam (GMT+7)
    vietnam_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now_vn = datetime.now(vietnam_tz)
    
    today = now_vn.strftime("%Y-%m-%d")
    today_count = sum(1 for ref in records if ref.get("timestamp", "").split("T")[0] == today)
    
    current_month = now_vn.strftime("%Y-%m")
    month_count = sum(1 for ref in records if ref.get("timestamp", "").startswith(current_month))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Danh sách đã mời", callback_data="list_invited")]
    ])

    await message.answer(
        f"🌹 Link mời của bạn: {referral_link}\n"
        f"Tổng lượt mời: {len(records)}\n"
        f"Lượt mời hôm nay: {today_count}\n"
        f"Lượt mời tháng này: {month_count}\n\n"
        "💰 Bạn nhận **2000 VNĐ** và **2% hoa hồng** từ số tiền cược của người được mời.",
        reply_markup=keyboard
    )

@router.callback_query(lambda callback: callback.data == "list_invited")
async def list_invited_handler(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    records = referrals.get(user_id, [])

    if not records:
        await callback.answer("❌ Bạn chưa mời ai.", show_alert=True)
        return

    invited_list = "\n".join(f"- {ref['user_id']}" for ref in records)
    await callback.message.answer(f"📋 **Danh sách ID đã mời:**\n{invited_list}")

# ===================== Hàm tính hoa hồng 2% =====================
async def add_commission(user_id: str, bet_amount: int):
    """
    Tìm người giới thiệu của user_id và cộng hoa hồng 2% từ tiền cược.
    """
    referrer_id = None
    for ref_id, referred_list in referrals.items():
        if any(ref["user_id"] == user_id for ref in referred_list):
            referrer_id = ref_id
            break
    if referrer_id:
        commission = int(bet_amount * 0.02)
        user_balance[referrer_id] = user_balance.get(referrer_id, 0) + commission
        save_data(data)
        try:
            await bot.send_message(referrer_id, f"🎉 Hoa hồng 2% từ cược của người chơi {user_id}: {commission} VNĐ!")
        except Exception as e:
            logging.error(f"Không thể gửi tin nhắn đến referrer_id {referrer_id}: {e}")

