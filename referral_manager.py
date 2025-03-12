import json
import os
import logging
from datetime import datetime
import pytz
from aiogram import Bot

# File lưu trữ danh sách mời
REFERRAL_FILE = "referrals.json"
USER_BALANCE_FILE = "user_balance.json"

# Load bot (truyền vào khi khởi tạo bot)
bot = None

# Hàm tải danh sách từ file JSON
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Hàm lưu danh sách vào file JSON
def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Load dữ liệu khi bot khởi động
referrals = load_json(REFERRAL_FILE)
user_balance = load_json(USER_BALANCE_FILE)

# Hàm thêm user vào danh sách referral
def add_referral(referrer_id, new_user_id):
    if referrer_id not in referrals:
        referrals[referrer_id] = []
    referrals[referrer_id].append({"user_id": new_user_id, "timestamp": datetime.now().isoformat()})
    save_json(REFERRAL_FILE, referrals)

# ===================== Hàm tính hoa hồng 2% =====================
async def add_commission(user_id: str, bet_amount: int):
    """
    Tìm người giới thiệu của user_id và cộng hoa hồng 2% từ tiền cược.
    """
    referrer_id = None
    for ref_id, referred_list in referrals.items():
        if any(ref["user_id"] == user_id for ref in referred_list):  # Kiểm tra xem user_id có trong danh sách không
            referrer_id = ref_id
            break

    if referrer_id:
        commission = int(bet_amount * 0.02)
        user_balance[referrer_id] = user_balance.get(referrer_id, 0) + commission
        save_json(USER_BALANCE_FILE, user_balance)

        try:
            await bot.send_message(referrer_id, f"🎉 Hoa hồng 2% từ cược của người chơi {user_id}: {commission} VNĐ!")
        except Exception as e:
            logging.error(f"Không thể gửi tin nhắn đến referrer_id {referrer_id}: {e}")
