import os
import json
import logging
import pytz
from datetime import datetime
from aiogram import types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

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

# Chuyển múi giờ Việt Nam
vietnam_tz = pytz.timezone("Asia/Ho_Chi_Minh")

def add_referral(referrer_id, new_user_id):
    referrer_id = str(referrer_id)
    new_user_id = str(new_user_id)
    
    if referrer_id not in referrals:
        referrals[referrer_id] = []
    
    # Kiểm tra nếu user đã tồn tại trong danh sách tránh trùng lặp
    if any(ref["user_id"] == new_user_id for ref in referrals[referrer_id]):
        return
    
    timestamp_vn = datetime.now(vietnam_tz).isoformat()
    referrals[referrer_id].append({"user_id": new_user_id, "timestamp": timestamp_vn})
    save_referrals()

# ===================== Hoa Hồng Handler =====================
@router.message(F.text == "🌹 Hoa hồng")
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

@router.callback_query(F.data == "list_invited")
async def list_invited_handler(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    records = referrals.get(user_id, [])

    if not records:
        await callback.answer("❌ Bạn chưa mời ai.", show_alert=True)
        return

    invited_list = "\n".join(f"- {ref['user_id']}" for ref in records)
    await callback.message.answer(f"📋 **Danh sách ID đã mời:**\n{invited_list}")
