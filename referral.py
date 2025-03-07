import json
from datetime import datetime

DATA_FILE = "user_data.json"

# Load dữ liệu từ file
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"balances": {}, "history": {}, "deposits": {}, "withdrawals": {}, "referrals": {}, "referral_earnings": {}}

# Lưu dữ liệu vào file
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
user_balance = data["balances"]
referrals = data.setdefault("referrals", {})  # Lưu danh sách người mời
referral_earnings = data.setdefault("referral_earnings", {})  # Lưu tiền hoa hồng

REFERRAL_BONUS = 2000  # Hoa hồng cố định 2k cho mỗi người được mời

def process_new_user(user_id, inviter_id):
    """ Xử lý khi có người mới tham gia bằng link mời """
    user_id = str(user_id)
    inviter_id = str(inviter_id)

    if user_id not in referrals and inviter_id != user_id:
        referrals[user_id] = inviter_id
        referral_earnings.setdefault(inviter_id, 0)
        referral_earnings[inviter_id] += REFERRAL_BONUS
        user_balance.setdefault(inviter_id, 0)
        user_balance[inviter_id] += REFERRAL_BONUS

        save_data(data)
        return True
    return False

def get_referral_info(user_id):
    """ Lấy thông tin hoa hồng của người dùng """
    user_id = str(user_id)
    referral_link = f"https://t.me/Bottx_Online_bot?start={user_id}"
    total_earnings = referral_earnings.get(user_id, 0)
    invite_count = sum(1 for uid in referrals if referrals[uid] == user_id)

    return referral_link, invite_count, total_earnings
