import logging
import asyncio
import random
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardMarkup,   # Dòng này
    InlineKeyboardButton    # và dòng này
)
import os
from aiogram.filters import Command
# File lưu trữ danh sách mời
REFERRAL_FILE = "referrals.json"

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
def add_referral(referrer_id, new_user_id):
    if referrer_id not in referrals:
        referrals[referrer_id] = []
    referrals[referrer_id].append({"user_id": new_user_id, "timestamp": datetime.now().isoformat()})
    save_json(REFERRAL_FILE, referrals)

# ===================== Cấu hình bot =====================
TOKEN = "7688044384:AAHi3Klk4-saK-_ouJ2E5y0l7TztKpUXEF0"
ADMIN_ID = 1985817060  # Thay ID admin của bạn
DATA_FILE = "user_data.json"

# Khởi tạo bot và dispatcher trước khi include router
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ===================== Hàm load/save dữ liệu =====================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {
            "balances": {},
            "history": {},
            "deposits": {},
            "withdrawals": {},
            "referrals": {},  # Danh sách người giới thiệu
            "banned_users": [],  # Danh sách user bị ban
            "current_id": 1
        }
    for key in ["balances", "history", "deposits", "withdrawals", "referrals", "banned_users"]:
        if key not in data:
            data[key] = {} if key != "banned_users" else []  # banned_users là list

    return data

def save_data(data):
    data["banned_users"] = list(banned_users)  # Chuyển set thành list để lưu JSON
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Load dữ liệu
data = load_data()
user_balance = data["balances"]
user_history = data["history"]
deposits = data["deposits"]
withdrawals = data["withdrawals"]
referrals = data["referrals"]
banned_users = set(data["banned_users"])  # Chuyển thành set để dễ xử lý
current_id = data["current_id"]

# ===================== Hàm lưu lịch sử cược chung =====================
def record_bet_history(user_id, game_name, bet_amount, result, winnings):
    """
    Lưu lại lịch sử cược của người chơi.
    - user_id: ID người chơi (str)
    - game_name: Tên game (ví dụ "Tài Xỉu", "Máy Bay", "Rồng Hổ", "Đào Vàng", "Mini Poker")
    - bet_amount: Số tiền cược
    - result: Kết quả (ví dụ "win", "lose", hoặc "rong - win")
    - winnings: Số tiền thắng (0 nếu thua)
    """
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "game": game_name,
        "bet_amount": bet_amount,
        "result": result,
        "winnings": winnings
    }
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append(record)
    save_data(data)
# ===================== Hàm tính hoa hồng 2% =====================
async def add_commission(user_id: str, bet_amount: int):
    """
    Tìm người giới thiệu của user_id và cộng hoa hồng 2% từ tiền cược.
    """
    logging.info(f"📌 Hàm add_commission được gọi - user_id: {user_id}, bet_amount: {bet_amount}")

    referrer_id = None
    for ref_id, referred_list in referrals.items():
        if any(ref["user_id"] == user_id for ref in referred_list):
            referrer_id = ref_id
            break

    if not referrer_id:
        logging.warning(f"⚠️ Không tìm thấy referrer của user {user_id}. Không thể cộng hoa hồng.")
        return

    commission = int(bet_amount * 0.07)
    user_balance[referrer_id] = user_balance.get(referrer_id, 0) + commission

    # Cập nhật số tiền hoa hồng trong danh sách mời
    for ref in referrals[referrer_id]:
        if ref["user_id"] == user_id:
            ref["commission"] = ref.get("commission", 0) + commission  # Cộng dồn hoa hồng
            break

    save_data(data)
    logging.info(f"✅ Hoa hồng {commission} VNĐ đã cộng cho {referrer_id}.")
    
# ===================== Các biến trạng thái =====================
taixiu_states = {}    # Trạng thái game Tài Xỉu
jackpot_states = {}   # Trạng thái game Jackpot
crash_states = {}     # Trạng thái game Máy Bay (Crash)
rongho_states = {}    # Trạng thái game Rồng Hổ
gold_states = {}      # Không dùng, vì game Đào Vàng dùng daovang_states
poker_states = {}     # Trạng thái game Mini Poker

# Các biến trạng thái cho giao dịch và game Đào Vàng
deposit_states = {}
daovang_states = {}

# ===================== Hệ thống VIP & Bonus =====================
vip_levels = {
    "VIP 1": 100000,
    "VIP 2": 500000,
    "VIP 3": 1000000,
    "VIP 4": 5000000,
    "VIP 5": 10000000,
}
NEW_USER_BONUS = 5000  # Tặng 5k cho người mới
MIN_BET = 1000         # Số tiền cược tối thiểu trong game Đào Vàng

# ===================== Hàm tính hệ số nhân cho game Đào Vàng =====================
def calculate_multiplier(safe_count, bomb_count):
    total_safe = 25 - bomb_count
    if safe_count >= total_safe:
        # Khi đã chọn hết ô an toàn, trả về hệ số tối đa (bằng tổng ô an toàn)
        return total_safe
    return total_safe / (total_safe - safe_count)

# ===================== Menus =====================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Danh sách game"), KeyboardButton(text="💰 Xem số dư")],
        [KeyboardButton(text="📜 Lịch sử cược"), KeyboardButton(text="🏧 Nạp tiền")],
        [KeyboardButton(text="💸 Rút tiền"), KeyboardButton(text="🌹 Hoa hồng")],
        [KeyboardButton(text="🏆 VIP"), KeyboardButton(text="💬 Hỗ trợ")]
    ],
    resize_keyboard=True
)

games_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎲 Tài Xỉu"), KeyboardButton(text="🎰 Jackpot")],
        [KeyboardButton(text="✈️ Máy Bay"), KeyboardButton(text="🐉 Rồng Hổ")],
        [KeyboardButton(text="⛏️ Đào Vàng"), KeyboardButton(text="🃏 Mini Poker")],
        [KeyboardButton(text="👥 Số người đang chơi")],  # Nút hiển thị số người đang chơi
        [KeyboardButton(text="🔙 Quay lại")]
    ],
    resize_keyboard=True
)

# ===================== Hàm set_bot_commands =====================
async def set_bot_commands(user_id: str):
    user_commands = [
        BotCommand(command="start", description="Bắt đầu bot"),
    ]
    admin_commands = user_commands + [
        BotCommand(command="naptien", description="Admin duyệt nạp tiền"),
        BotCommand(command="xacnhan", description="Admin duyệt rút tiền"),
        BotCommand(command="congtien", description="Cộng tiền cho người dùng (Admin)"),
        BotCommand(command="setplayers", description="Chỉnh số người chơi ảo"),
        BotCommand(command="unlockplayers", description="Mở khóa số người chơi"),
        BotCommand(command="tracuu", description="Xem người chơi (Admin)")
    ]
    if user_id == str(ADMIN_ID):
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=int(user_id)))
    else:
        await bot.set_my_commands(user_commands, scope=BotCommandScopeChat(chat_id=int(user_id)))

# ===================== /start Handler =====================
@router.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = str(message.from_user.id)

    # Hàm chuyển đổi số tiền thành định dạng dễ đọc
    def format_money(amount):
        if amount >= 1_000_000_000:
            return f"{amount / 1_000_000_000:.2f} Tỷ VNĐ"
        elif amount >= 1_000_000:
            return f"{amount / 1_000_000:.2f} Triệu VNĐ"
        elif amount >= 1_000:
            return f"{amount / 1_000:.0f}K VNĐ"
        else:
            return f"{amount} VNĐ"

    # Kiểm tra nếu người chơi bị ban
    if user_id in banned_users:
        balance = user_balance.get(user_id, 0)  # Lấy số dư của user
        formatted_balance = format_money(balance)  # Định dạng số dư

        logging.warning(f"[BAN] Người dùng {user_id} bị khóa tài khoản. Số dư: {formatted_balance}")

        await message.answer(
            f"⚠️ Tài khoản Mega6casino của bạn đã bị khóa vì vi phạm quy định.\n"
            f"💰 Số dư hiện tại: {formatted_balance}.\n"
            f"Để mở khóa, vui lòng liên hệ hỗ trợ.",
            reply_markup=types.ReplyKeyboardRemove()  # Xóa toàn bộ nút
        )
        return

    await set_bot_commands(user_id)
    parts = message.text.split()
    referrer_id = parts[1] if len(parts) > 1 else None

    new_user = False
    if user_id not in user_balance:
        user_balance[user_id] = 5000  # Tặng 5.000 VNĐ khi đăng ký mới
        user_history[user_id] = []
        deposits[user_id] = []
        withdrawals[user_id] = []
        save_data(data)
        new_user = True

        # Nếu có referral và người giới thiệu hợp lệ, cộng bonus 2k cho họ
        if referrer_id and referrer_id != user_id:
            if referrer_id not in referrals:
                referrals[referrer_id] = []
            if user_id not in [ref["user_id"] for ref in referrals[referrer_id]]:
                referrals[referrer_id].append({
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                })
                user_balance[referrer_id] = user_balance.get(referrer_id, 0) + 2000
                save_data(data)
                try:
                    await bot.send_message(referrer_id, "🎉 Bạn vừa nhận 2.000 VNĐ vì mời được một người chơi mới!")
                except Exception as e:
                    logging.error(f"Không thể gửi tin nhắn đến referrer_id {referrer_id}: {e}")

    # Hiển thị giao diện
    if new_user:
        welcome_text = (
            "👋 Chào mừng bạn đến với *Mega6 Casino*!\n"
            "Bot game an toàn và bảo mật, nơi bạn có thể trải nghiệm 6 trò chơi hấp dẫn:\n"
            "• Tài Xỉu\n"
            "• Jackpot\n"
            "• Máy Bay\n"
            "• Rồng Hổ\n"
            "• Đào Vàng\n"
            "• Mini Poker\n\n"
            "Bạn vừa được tặng 5.000 VNĐ vào số dư để bắt đầu. Chúc bạn may mắn!"
        )
        await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_menu)
    else:
        await message.answer("👋 Chào mừng bạn quay lại!", reply_markup=main_menu)

# ===================== VIP Handler =====================
@router.message(F.text == "🏆 VIP")
async def vip_info(message: types.Message):
    user_id = str(message.from_user.id)
    full_name = message.from_user.full_name 
    username = message.from_user.username
    
    total_deposit = sum(deposit.get("amount", 0) for deposit in deposits.get(user_id, []) if deposit.get("status") == "completed")
    current_vip = "Chưa đạt VIP nào"

    for vip, req_amount in sorted(vip_levels.items(), key=lambda x: x[1]):
        if total_deposit >= req_amount:
            current_vip = vip

    # Định dạng số tiền với dấu phẩy
    formatted_total_deposit = f"{total_deposit:,}"
    
    user_display = f"{username}" if username else full_name
    
    await message.answer(
        f"🏆 VIP của bạn: {current_vip}\n"
        f"👤 Tên người dùng: {user_display}\n"
        f"👥 ID tài khoản: {user_id}\n"
        f"💰 Tổng nạp: {formatted_total_deposit} VNĐ",
        reply_markup=main_menu
    )

from datetime import datetime, timedelta
import pytz

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
         "💰 Bạn nhận 2000 VNĐ và 7% hoa hồng từ số tiền cược của người được mời.",
         reply_markup=keyboard
    )

@router.callback_query(F.data == "list_invited")
async def list_invited_handler(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    records = referrals.get(user_id, [])

    if not records:
        await callback.answer("❌ Bạn chưa mời ai.", show_alert=True)
        return

    invited_list = "\n".join(
        f"- {ref['user_id']} (+{ref.get('commission', 0):,} VNĐ)" for ref in records
    )
    
    await callback.message.answer(f"📋 **Danh sách ID đã mời:**\n{invited_list}")
    
# ===================== Danh sách game Handler =====================
@router.message(F.text == "🎮 Danh sách game")
async def show_games(message: types.Message):
    user_id = str(message.from_user.id)
    deposit_states[user_id] = None
    await message.answer("Danh sách game:", reply_markup=games_menu)

@router.message(F.text == "🔙 Quay lại")
async def back_to_main(message: types.Message):
    await message.answer("Quay lại menu chính", reply_markup=main_menu)

# ===================== Xem số dư & Lịch sử Handler =====================
@router.message(F.text == "💰 Xem số dư")
async def check_balance(message: types.Message):
    user_id = str(message.from_user.id)
    balance = user_balance.get(user_id, 0)

    # Chuyển đổi số dư sang định dạng dễ đọc
    def format_money(amount):
        if amount >= 1_000_000_000:
            return f"{amount / 1_000_000_000:.2f} Tỷ VNĐ"
        elif amount >= 1_000_000:
            return f"{amount / 1_000_000:.2f} Triệu VNĐ"
        elif amount >= 1_000:
            return f"{amount / 1_000:.0f}K VNĐ"
        else:
            return f"{amount} VNĐ"

    formatted_balance = format_money(balance)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="💸 Lịch sử rút", callback_data="withdraw_history")
    kb.button(text="📥 Lịch sử nạp", callback_data="deposit_history")
    kb.button(text="👥 Chuyển tiền", callback_data="transfer_money")
    kb.adjust(1)

    await message.answer(f"💰 Số dư hiện tại của bạn: {formatted_balance}", reply_markup=kb.as_markup())

import time
import pytz
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command

# Giả sử main_menu và user_history đã được định nghĩa ở nơi khác
# Ví dụ:
# main_menu = ReplyKeyboardMarkup(keyboard=[...], resize_keyboard=True)
# user_history = {}  # Dictionary lưu lịch sử cược của người dùng

def parse_timestamp(ts):
    """Hàm chuyển đổi timestamp sang float; nếu không hợp lệ trả về thời gian hiện tại."""
    try:
        return float(ts)
    except (TypeError, ValueError):
        return time.time()

@router.message(F.text == "📜 Lịch sử cược")
async def bet_history(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_history or not user_history[user_id]:
        await message.answer("📜 Bạn chưa có lịch sử cược.", reply_markup=main_menu)
        return

    vietnam_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    history_list = user_history[user_id][-10:]
    
    text = "\n".join([
        f"⏰ {datetime.fromtimestamp(parse_timestamp(r.get('timestamp')), vietnam_tz).strftime('%Y-%m-%d %H:%M:%S')}: "
        f"{r.get('game', 'Unknown')} - Cược {r.get('bet_amount', 0):,} VNĐ\n"
        f"🔹 Kết quả: {r.get('result', '?')} | "
        f"🏆 Thắng/Thua: {r.get('winnings', 0):,} VNĐ"
        for r in history_list
    ])

    await message.answer(f"📜 *Lịch sử cược gần đây của bạn:*\n{text}", reply_markup=main_menu, parse_mode="Markdown")

# ===================== Handler Hỗ trợ =====================
@router.message(F.text == "💬 Hỗ trợ")
async def support_handler(message: types.Message):
    support_text = (
        "📞 **Hỗ trợ Mega6casino**\n\n"
        "Nếu bạn gặp khó khăn hoặc cần trợ giúp, vui lòng liên hệ:\n"
        "- Liên hệ: @hoanganh11829\n\n"
    )
    await message.answer(support_text, reply_markup=main_menu)

from aiogram import Bot
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import types, Router
from aiogram.types import Message
from aiogram.filters import CommandStart

# Định nghĩa trạng thái FSM cho chuyển tiền
class TransferState(StatesGroup):
    waiting_for_receiver = State()
    waiting_for_amount = State()

# ===================== Chuyển Tiền Handler ===================== 
@router.callback_query(F.data == "transfer_money")
async def transfer_money_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔹Nhập ID người nhận trước:\n💡 Lưu ý: Chuyển tiền sẽ mất phí 3% và tối thiểu 20,000 VNĐ.")
    await state.set_state(TransferState.waiting_for_receiver)
    await callback.answer()
        
@router.message(TransferState.waiting_for_receiver)
async def enter_receiver_id(message: types.Message, state: FSMContext):
    receiver_id = message.text.strip()

    # Kiểm tra xem user có nhập số hợp lệ không
    if not receiver_id.isdigit():
        await message.answer("❌ ID không hợp lệ. Quay lại menu chính.", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Quay lại", callback_data="main_menu")]]
        ))
        await state.clear()
        return
    
    await state.update_data(receiver_id=receiver_id)
    await message.answer("💰 Nhập số tiền muốn chuyển:")
    await state.set_state(TransferState.waiting_for_amount)

@router.message(TransferState.waiting_for_amount)
async def enter_transfer_amount(message: types.Message, state: FSMContext, bot: Bot):
    amount = message.text.strip()
    
    if not amount.isdigit() or int(amount) < 20000:
        await message.answer("❌ Số tiền không hợp lệ. Quay lại menu chính.", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Quay lại", callback_data="main_menu")]]
        ))
        await state.clear()
        return
    
    user_id = str(message.from_user.id)
    receiver_data = await state.get_data()
    receiver_id = receiver_data["receiver_id"]
    amount = int(amount)
    fee = int(amount * 0.03)  # Phí 3%
    total_deduction = amount + fee
    
    # Kiểm tra số dư
    if user_balance.get(user_id, 0) < total_deduction:
        await message.answer("❌ Số dư không đủ để thực hiện giao dịch. Quay lại menu chính.", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Quay lại", callback_data="main_menu")]]
        ))
        await state.clear()
        return
    
    # Thực hiện chuyển tiền
    user_balance[user_id] -= total_deduction
    user_balance[receiver_id] = user_balance.get(receiver_id, 0) + amount
    
    await message.answer(f"✅ Bạn đã chuyển thành công {amount} VNĐ cho ID {receiver_id}. (Phí: {fee} VNĐ)")
    await bot.send_message(receiver_id, f"💰 Bạn đã nhận {amount} VNĐ từ ID {user_id}.")
    
    await state.clear()
    
# ===================== GAME: Tài Xỉu =====================
# ✅ Ghi log chi tiết các hành động của người chơi
def log_action(user_id, action, details=""):
    log_data = {
        "user_id": user_id,
        "action": action,
        "details": details
    }
    logging.info(json.dumps(log_data, ensure_ascii=False))

MIN_BET = 1_000  # Cược tối thiểu 1,000 VNĐ
MAX_BET = 10_000_000  # Cược tối đa 10 triệu VNĐ
COMBO_MULTIPLIERS = {"triple": 30, "specific": 3}  # Tỷ lệ thưởng

# Hàm ghi log chi tiết
def log_action(user_id, action, details=""):
    log_data = {
        "user_id": user_id,
        "action": action,
        "details": details
    }
    logging.info(json.dumps(log_data, ensure_ascii=False))

@router.message(F.text == "/huy")
async def cancel_bet(message: types.Message):
    """Cho phép người chơi hủy ván cược nếu bị kẹt"""
    user_id = str(message.from_user.id)
    log_action(user_id, "Hủy cược")
    if user_id in taixiu_states:
        del taixiu_states[user_id]
        await message.answer("✅ Bạn đã hủy ván cược! Bây giờ bạn có thể đặt cược mới.")
    else:
        await message.answer("❌ Bạn không có ván cược nào đang chờ.")

@router.message(F.text == "🎲 Tài Xỉu")
async def start_taixiu(message: types.Message):
    user_id = str(message.from_user.id)
    log_action(user_id, "Bắt đầu chơi Tài Xỉu", "Chờ chọn loại cược")
    # Chặn spam cược liên tục
    if user_id in taixiu_states:
        await message.answer("⏳ Bạn đang có một ván cược chưa hoàn tất. Nhập /huy để hủy cược trước khi chơi lại!")
        return
    taixiu_states[user_id] = "awaiting_choice"
    await message.answer(
        "🎲 **Tài Xỉu**:\n"
        "- Tài (11-18) / Xỉu (3-10): x1.98.\n"
        "- Bộ Ba 🎲 (3 số giống): x30.\n"
        "- Cược Số 🎯 (số xuất hiện): x3.\n"
        "👉 Chọn loại cược của bạn!",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Tài"), KeyboardButton(text="Xỉu")],
                [KeyboardButton(text="Bộ Ba 🎲"), KeyboardButton(text="Cược Số 🎯")]
            ],
            resize_keyboard=True
        ),
        parse_mode="Markdown"
    )

@router.message(lambda msg: taixiu_states.get(str(msg.from_user.id)) == "awaiting_choice" and msg.text in ["Tài", "Xỉu", "Bộ Ba 🎲", "Cược Số 🎯"])
async def choose_taixiu(message: types.Message):
    user_id = str(message.from_user.id)
    log_action(user_id, "Chọn loại cược", message.text)
    # Chặn chọn lại nhiều lần
    if isinstance(taixiu_states.get(user_id), dict):
        await message.answer("⏳ Bạn đã đặt cược. Vui lòng nhập số tiền cược!")
        return
    if message.text in ["Bộ Ba 🎲", "Cược Số 🎯"]:
        taixiu_states[user_id] = {"choice": message.text, "state": "awaiting_combo_choice"}
        await message.answer("🔢 Hãy chọn một số từ 1 đến 6 để đặt cược:", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=str(i)) for i in range(1, 7)]], resize_keyboard=True))
    else:
        taixiu_states[user_id] = {"choice": message.text, "state": "awaiting_bet"}
        await message.answer(f"✅ Bạn đã chọn {message.text}. Vui lòng nhập số tiền cược:", reply_markup=ReplyKeyboardRemove())

@router.message(lambda msg: isinstance(taixiu_states.get(str(msg.from_user.id)), dict)
                          and taixiu_states[str(msg.from_user.id)].get("state") == "awaiting_combo_choice"
                          and msg.text in [str(i) for i in range(1, 7)])
async def choose_combo_number(message: types.Message):
    user_id = str(message.from_user.id)
    chosen_number = int(message.text)
    taixiu_states[user_id]["number"] = chosen_number
    taixiu_states[user_id]["state"] = "awaiting_bet"
    bet_type = taixiu_states[user_id]["choice"]
    multiplier = 30 if bet_type == "Bộ Ba 🎲" else 3
    log_action(user_id, "Chọn số cược", f"{bet_type} - Số {chosen_number}")
    await message.answer(
        f"✅ Bạn đã chọn số {message.text} cho {bet_type}.\n"
        f"💰 Nếu {message.text} xuất hiện **{'3 lần' if bet_type == 'Bộ Ba 🎲' else 'ít nhất 1 lần'}, bạn sẽ thắng {multiplier}x tiền cược**.\n"
        "Vui lòng nhập số tiền cược:"
    )
@router.message(lambda msg: isinstance(taixiu_states.get(str(msg.from_user.id)), dict)
                          and taixiu_states[str(msg.from_user.id)].get("state") == "awaiting_bet"
                          and msg.text.isdigit())
async def play_taixiu(message: types.Message):
    user_id = str(message.from_user.id)
    bet_amount = int(message.text)
    log_action(user_id, "Đặt cược", f"{taixiu_states[user_id]['choice']} - Số {taixiu_states[user_id].get('number', 'N/A')} - {bet_amount:,} VNĐ")
    
    # Kiểm tra số tiền cược hợp lệ
    if bet_amount < MIN_BET or bet_amount > MAX_BET:
        await message.answer(f"❌ Số tiền cược phải từ {MIN_BET:,} VNĐ đến {MAX_BET:,} VNĐ!")
        return
    if user_balance.get(user_id, 0) < bet_amount:
        await message.answer("❌ Số dư không đủ!")
        del taixiu_states[user_id]
        return
    
    # Trừ tiền cược và tính hoa hồng
    user_balance[user_id] -= bet_amount
    save_data(data)
    await add_commission(user_id, bet_amount)
    logging.info(f"Người dùng {user_id} cược {bet_amount:,} VNĐ. Số dư còn lại: {user_balance[user_id]:,} VNĐ.")
    
    # Xúc xắc quay
    dice_values = []
    for i in range(3):
        dice_msg = await message.answer_dice(emoji="🎲")
        await asyncio.sleep(2)
        if not dice_msg.dice:
            await message.answer("⚠️ Lỗi hệ thống, vui lòng thử lại!")
            del taixiu_states[user_id]
            return
        dice_values.append(dice_msg.dice.value)
    
    total = sum(dice_values)
    result = "Tài" if total >= 11 else "Xỉu"
    user_choice = taixiu_states[user_id]["choice"]
    
    # Kiểm tra kết quả
    win_amount = 0
    outcome_text = ""
    if user_choice in ["Tài", "Xỉu"]:
        if user_choice == result:
            win_amount = int(bet_amount * 1.98)
    elif user_choice == "Bộ Ba 🎲":
        chosen_number = taixiu_states[user_id]["number"]
        if dice_values.count(chosen_number) == 3:
            win_amount = bet_amount * COMBO_MULTIPLIERS["triple"]
    elif user_choice == "Cược Số 🎯":
        chosen_number = taixiu_states[user_id]["number"]
        if chosen_number in dice_values:
            win_amount = bet_amount * COMBO_MULTIPLIERS["specific"]
    
    if win_amount > 0:
        user_balance[user_id] += win_amount
        save_data(data)
        outcome_text = f"🔥 Bạn thắng {win_amount:,} VNĐ!"
        logging.info(f"[INFO] Tiền thưởng {win_amount:,} VNĐ đã được cộng. Số dư mới: {user_balance[user_id]:,} VNĐ.")
    else:
        outcome_text = f"😢 Bạn thua {bet_amount:,} VNĐ!"
    
    log_action(user_id, "Kết quả cược", f"Xúc xắc: {dice_values}, Tổng: {total}, Kết quả: {result}, {outcome_text}")
    
    # Gửi kết quả
    await message.answer(f"🎲 Kết quả: {dice_values}\n✨ Tổng: {total} ({result})\n{outcome_text}")
    
    # Lưu lịch sử cược
    record_bet_history(user_id, "Tài Xỉu", bet_amount, f"{result} - {'win' if win_amount > 0 else 'lose'}", win_amount)
    
    # Xóa trạng thái cược
    del taixiu_states[user_id]

# ===================== GAME: Jackpot =====================
jackpot_states = {}

# 🏆 Các biểu tượng Jackpot
slot_symbols = ["🍒", "🍏", "🍇", "🍉", "7️⃣", "⭐"]

# 🎰 Tỷ lệ thưởng Jackpot
jackpot_rewards = {
    "🍒🍒🍒": 3,
    "🍏🍏🍏": 5,
    "🍇🍇🍇": 5,
    "🍉🍉🍉": 10,
    "⭐⭐⭐": 10,
    "7️⃣7️⃣7️⃣": 15  # 🎰 Jackpot lớn nhất!
}

async def spin_effect(message, slots):
    """ 🌀 Hiệu ứng quay chậm dần """
    display = ["❔", "❔", "❔"]  # Biểu tượng lúc đầu
    current_text = ""  # Biến lưu nội dung hiện tại của tin nhắn

    for i in range(3):
        for _ in range(5):  # Quay nhanh 5 lần
            display[i] = random.choice(slot_symbols)
            new_text = f"🎰 Kết quả: {display[0]} {display[1]} {display[2]}"
            # Kiểm tra xem tin nhắn mới có khác với tin nhắn hiện tại không
            if new_text != current_text:
                await message.edit_text(new_text)
                current_text = new_text
            await asyncio.sleep(0.2)  # Tăng tốc độ quay
        display[i] = slots[i]  # Chốt kết quả sau mỗi lần quay
        new_text = f"🎰 Kết quả: {display[0]} {display[1]} {display[2]}"
        # Kiểm tra lại và cập nhật tin nhắn nếu có sự thay đổi
        if new_text != current_text:
            await message.edit_text(new_text)
            current_text = new_text
        await asyncio.sleep(0.6)  # Quay chậm lại sau khi chốt kết quả

async def spin_game(message):
    # Kết quả quay ngẫu nhiên
    slot_result = [random.choice(slot_symbols) for _ in range(3)]
    print(f"Slot Result: {slot_result}")  # Kiểm tra kết quả
    await spin_effect(message, slot_result)
    return slot_result  # Trả về kết quả quay

@router.message(F.text == "🎰 Jackpot")
async def jackpot_game(message: types.Message):
    """ Bắt đầu trò chơi Jackpot """
    user_id = str(message.from_user.id)
    log_action(user_id, "Bắt đầu chơi Jackpot", "Chờ nhập số tiền cược")
    jackpot_states[user_id] = True

    # Gửi tin nhắn hướng dẫn trước khi yêu cầu nhập tiền cược
    await message.answer(
        "🎰 **Jackpot**:\n"
        "- Quay 3 biểu tượng, trùng 3 giống nhau để thắng.\n"
        "- Thưởng: 🍒x3, 🍏x5, 🍇x5, 🍉x10, ⭐x10, 7️⃣x15.\n"
        "💰 Nhập số tiền cược (tối thiểu 1,000 VNĐ):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

@router.message(lambda msg: jackpot_states.get(str(msg.from_user.id)) == True and msg.text.isdigit())
async def jackpot_bet(message: types.Message):
    """ Người chơi nhập số tiền cược và quay Jackpot """
    user_id = str(message.from_user.id)
    bet_amount = int(message.text)
    log_action(user_id, "Đặt cược", f"{bet_amount:,} VNĐ")

    # Kiểm tra số tiền cược tối thiểu là 1,000 VNĐ
    if bet_amount < 1000:
        await message.answer("❌ Số tiền cược tối thiểu là 1,000 VNĐ!")
        log_action(user_id, "Lỗi cược", "Số tiền cược dưới mức tối thiểu")
        return

    # Kiểm tra số dư
    if user_balance.get(user_id, 0) < bet_amount:
        await message.answer("❌ Số dư không đủ!")
        jackpot_states[user_id] = False
        return

    # Trừ tiền cược
    user_balance[user_id] -= bet_amount
    save_data(user_balance)  # Lưu dữ liệu
    await add_commission(user_id, bet_amount)
    
    # Bắt đầu hiệu ứng quay
    spin_message = await message.answer("🎰 Đang quay Jackpot...")
    await asyncio.sleep(1)

    # Quay ngẫu nhiên 3 ô
    slot_result = await spin_game(spin_message)

    # Xác định kết quả thắng/thua
    win_amount = 0
    result_text = "😢 Rất tiếc, bạn không trúng Jackpot."
    slot_str = "".join(slot_result)  # Ghép chuỗi kết quả

    if slot_str in jackpot_rewards:
        multiplier = jackpot_rewards[slot_str]
        win_amount = bet_amount * multiplier
        user_balance[user_id] += win_amount
        save_data(user_balance)
        result_text = f"🎉 Chúc mừng! Bạn trúng x{multiplier}!\n💰 Nhận được: {win_amount:,} VNĐ!"

    # Ghi log kết quả
    log_action(user_id, "Kết quả quay", f"Kết quả: {slot_str}, {result_text}")

    # Gửi kết quả
    await spin_message.edit_text(
        f"🎰 Kết quả cuối:\n{slot_result[0]} | {slot_result[1]} | {slot_result[2]}\n\n{result_text}\n💰 Số dư hiện tại: {user_balance[user_id]:,} VNĐ",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎲 Chơi tiếp", callback_data="play_jackpot_again")
            ]]
        )
    )

    # Lưu lịch sử cược
    record_bet_history(user_id, "Jackpot", bet_amount, slot_str, win_amount)
    jackpot_states[user_id] = False

@router.callback_query(F.data == "play_jackpot_again")
async def play_again_jackpot(callback: types.CallbackQuery):
    """ Xử lý khi người chơi chọn 'Chơi tiếp' """
    user_id = str(callback.from_user.id)
    log_action(user_id, "Chơi lại", "Người chơi bấm 'Chơi tiếp'")

    # Gửi tin nhắn hướng dẫn lại một lần nữa, thay đổi nội dung để tránh bị trùng
    await callback.message.edit_text(
        "🎰 Đang bắt đầu lại trò chơi Jackpot...\n\n"
        "💰 Nhập số tiền bạn muốn cược (Tối thiểu 1,000 VNĐ):"
    )

    # Thay đổi trạng thái để chấp nhận cược mới
    jackpot_states[user_id] = True  # Bật lại trạng thái cho phép cược

    # Gửi yêu cầu nhập số tiền cược lại
    await callback.answer()

import random
import asyncio
import logging
from aiogram import types, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

# --- GAME: Máy Bay (Crash Game) ---
crash_states = {}
crash_games = {}
user_balance = {}  # Lưu số dư người dùng

# Hàm save_data, record_bet_history, add_commission, main_menu ... được định nghĩa bên ngoài

@router.message(F.text == "✈️ Máy Bay")
async def start_crash(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Kiểm tra nếu người dùng đang trong trạng thái chơi game
    if crash_states.get(user_id, False):
        await message.answer("✈️ Bạn đang trong game! Hãy đặt cược nhé!")
        return
    
    # Nếu không đang chơi, tiếp tục logic bắt đầu game
    crash_states[user_id] = True
    logging.info(f"Người dùng {user_id} bắt đầu chơi Máy Bay✈️.")
    
    # Lấy số người chơi hiện tại cho game "✈️ Máy Bay"
    players_count = game_players.get("✈️ Máy Bay", "không xác định")
    
    # Phần giải thích cách chơi ngắn gọn
    game_explanation = (
        " ✈️ *Cách chơi Máy Bay:*\n"
        "1. Bạn Đặt cược và chờ máy bay cất cánh.\n"
        "2. Máy bay sẽ cất cánh và hệ số nhân sẽ tăng dần.\n"
        "3. Nhấn '💸 Rút tiền máy bay' trước khi máy bay rơi để nhận thưởng .\n"
        "4. Nếu không rút kịp, bạn sẽ mất số tiền cược.\n"
    )
    
    await message.answer(
        f"{game_explanation}\n\n"
        f"💰 Nhập số tiền cược (tối thiểu 1.000 VNĐ), bot sẽ khởi động máy bay!\n"
        f"👥 Hiện có {players_count} người đang chơi game này.",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: crash_states.get(str(msg.from_user.id), False) and msg.text.isdigit())
async def initiate_crash_game(message: types.Message):
    user_id = str(message.from_user.id)
    bet = int(message.text)

    if bet < 1000 or bet > 10000000:
        logging.warning(f"Người dùng {user_id} nhập số tiền cược không hợp lệ: {bet}")
        await message.answer("❌ Cược hợp lệ từ 1.000 VNĐ tối đa đến 10.000.000 VNĐ!", reply_markup=main_menu)
        crash_states[user_id] = False
        return

    if user_balance.get(user_id, 0) < bet:
        logging.warning(f"Người dùng {user_id} không đủ tiền. Số dư: {user_balance.get(user_id, 0)}, Cược: {bet}")
        await message.answer("❌ Số dư không đủ!", reply_markup=main_menu)
        crash_states[user_id] = False
        return

    # Trừ tiền cược
    user_balance[user_id] -= bet
    save_data(user_balance)
    await add_commission(user_id, bet)
    logging.info(f"Người dùng {user_id} cược {bet:,} VNĐ. Số dư còn lại: {user_balance[user_id]:,} VNĐ.")
    
    # Xác định crash_point ngẫu nhiên (1.1 - 15.0)
    crash_point = round(random.uniform(1.1, 25.0), 2)
    logging.info(f"Máy bay của {user_id} sẽ rơi tại x{crash_point}.")
    withdraw_event = asyncio.Event()

    crash_games[user_id] = {
        "bet": bet,
        "current_multiplier": 1.0,
        "running": True,
        "crash_point": crash_point,
        "withdraw_event": withdraw_event,
        "message_id": None
    }

    await run_crash_game(message, user_id)

async def run_crash_game(message: types.Message, user_id: str):
    bet = crash_games[user_id]["bet"]

    countdown_time = random.choice([5, 7, 9, 12])
    logging.info(f"[{user_id}] Bắt đầu đếm ngược: {countdown_time} giây.")

    countdown_message = await message.answer(f"⏳ Máy bay sẽ cất cánh trong {countdown_time} giây...")
    
    for i in range(countdown_time, 0, -1):
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=countdown_message.message_id,
                text=f"⏳ Máy bay sẽ cất cánh trong {i} giây..."
            )
            logging.info(f"[{user_id}] Cập nhật đếm ngược: {i} giây còn lại.")
        except Exception as e:
            logging.error(f"[{user_id}] Lỗi khi cập nhật tin nhắn đếm ngược: {e}")
        await asyncio.sleep(1)

    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=countdown_message.message_id)
    except Exception as e:
        logging.error(f"[{user_id}] Lỗi khi xóa tin nhắn đếm ngược: {e}")

    crash_keyboard = InlineKeyboardMarkup(inline_keyboard=[
         [InlineKeyboardButton(text="💸 Rút tiền máy bay", callback_data="withdraw_crash")]
    ])

    sent_message = await message.answer(
         f"✈️ Máy bay đang cất cánh...\n📈 Hệ số nhân: x1.00",
         reply_markup=crash_keyboard
    )
    crash_games[user_id]["message_id"] = sent_message.message_id

    start_time = time.time()
    base_increment = 0.01  # Giá trị tăng cơ bản
    acceleration = 1.03  # Hệ số tăng tốc

    last_multiplier = None  # Lưu hệ số trước đó

    logging.info(f"[{user_id}] Máy bay đã cất cánh!")

    while crash_games[user_id]["running"]:
        elapsed_time = time.time() - start_time
        current_multiplier = round(1 + elapsed_time * base_increment, 2)

        # Tăng tốc hệ số sau một thời gian
        if elapsed_time > 3:
            base_increment *= acceleration  # Tăng tốc dần

        crash_games[user_id]["current_multiplier"] = current_multiplier

        # Kiểm tra người chơi có rút tiền không
        try:
            await asyncio.wait_for(crash_games[user_id]["withdraw_event"].wait(), timeout=0.1)
            if crash_games[user_id]["withdraw_event"].is_set():
                win_amount = round(bet * crash_games[user_id]["current_multiplier"])
                user_balance[user_id] += win_amount
                save_data(user_balance)
                logging.info(f"[{user_id}] Rút tiền thành công! Hệ số: x{crash_games[user_id]['current_multiplier']} - Nhận: {win_amount:,} VNĐ.")
               
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=crash_games[user_id]["message_id"],
                        text=f"🎉 Bạn đã rút tiền thành công! Nhận {win_amount:,} VNĐ!",
                        reply_markup=None
                    )
                except Exception as e:
                    logging.error(f"[{user_id}] Lỗi khi cập nhật tin nhắn rút tiền: {e}")
                    record_bet_history(user_id, "Máy Bay", bet, "win", win_amount)
                break
        except asyncio.TimeoutError:
            pass  # Không có ai rút, tiếp tục tăng hệ số

        # Kiểm tra xem máy bay có rơi không
        if current_multiplier >= crash_games[user_id]["crash_point"]:
            logging.info(f"[{user_id}] Máy bay rơi tại x{crash_games[user_id]['crash_point']}! Người chơi mất {bet:,} VNĐ.")

            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=crash_games[user_id]["message_id"],
                    text=f"💥 <b>Máy bay rơi tại</b> x{crash_games[user_id]['crash_point']}!\n❌ Bạn đã mất {bet:,} VNĐ!",
                    parse_mode="HTML",
                    reply_markup=None
                )
            except Exception as e:
                logging.error(f"[{user_id}] Lỗi khi cập nhật tin nhắn thua: {e}")
            record_bet_history(user_id, "Máy Bay", bet, "lose", 0)
            break

        # **Chỉ cập nhật tin nhắn nếu hệ số thay đổi thực sự**
        if current_multiplier != last_multiplier:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=crash_games[user_id]["message_id"],
                    text=f"✈️ Máy bay đang bay...\n📈 Hệ số nhân: x{current_multiplier}",
                    reply_markup=crash_keyboard
                )
                logging.info(f"[{user_id}] Cập nhật hệ số nhân: x{current_multiplier}")
                last_multiplier = current_multiplier  # Cập nhật giá trị cũ
            except Exception as e:
                logging.error(f"[{user_id}] Lỗi khi cập nhật hệ số nhân: {e}")

        await asyncio.sleep(0.1)  # Cập nhật nhanh hơn để tạo cảm giác mượt

    crash_states[user_id] = False
    crash_games.pop(user_id, None)
    await message.answer("🏠 Quay về menu chính.", reply_markup=main_menu)
    
@router.callback_query(lambda c: c.data == "withdraw_crash")
async def withdraw_crash(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    
    if user_id in crash_games and crash_games[user_id]["running"]:
        bet = crash_games[user_id]["bet"]
        multiplier = crash_games[user_id]["current_multiplier"]

        # Lợi nhuận thực tế (không tính lại tiền cược ban đầu)
        profit = round(bet * (multiplier - 1))  

        # Cộng lại đúng phần lợi nhuận (không cộng lại cả vốn)
        user_balance[user_id] += profit  
        save_data(user_balance)
        logging.info(f"Người dùng {user_id} rút tiền tại x{multiplier}. Nhận {profit:,} VNĐ.")
        record_bet_history(user_id, "Máy Bay", bet, "win", profit)

        crash_games[user_id]["running"] = False
        crash_games[user_id]["withdraw_event"].set()

        try:
            await callback.message.edit_text(
                f"🎉 Bạn đã rút tiền thành công!\n💰 Nhận: {profit:,} VNĐ!\n📈 Hệ số nhân: x{multiplier}",
                reply_markup=None
            )
        except Exception as e:
            logging.error(f"Lỗi khi cập nhật tin nhắn rút tiền: {e}")

        await callback.answer(f"💸 Bạn đã rút {profit:,} VNĐ lợi nhuận thành công!")

    else:
        await callback.answer("⚠️ Không thể rút tiền ngay bây giờ!")

    # Fix lỗi KeyError nếu user không còn trong crash_games
    if user_id in crash_games and crash_games[user_id]["running"]:
        await run_crash_game(callback.message, user_id)

# ===================== Handler bắt đầu game Rồng Hổ =====================
@router.message(F.text == "🐉 Rồng Hổ")
async def start_rongho(message: types.Message):
    user_id = str(message.from_user.id)
    log_action(user_id, "Bắt đầu chơi 🐉 Rồng Hổ", "Chờ chọn cửa cược")

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🐉 Rồng"), KeyboardButton(text="⚖️ Hòa"), KeyboardButton(text="🐅 Hổ")]
        ],
        resize_keyboard=True
    )

    # Thêm giải thích game
    game_explanation = (
        "🎲 **Rồng Hổ**:\n"
        "- Chọn: 🐉 Rồng, 🐅 Hổ, ⚖️ Hòa.\n"
        "- Bài lớn hơn thắng, bằng là Hòa.\n"
        "- Thưởng: Rồng/Hổ x1.98, Hòa x7.98.\n"
        "👉 Chọn cửa cược của bạn!"
    )

    rongho_states[user_id] = "awaiting_choice"
    await message.answer(game_explanation, parse_mode="Markdown", reply_markup=keyboard)
# ===================== Handler chọn cửa cược =====================
@router.message(lambda msg: rongho_states.get(str(msg.from_user.id)) == "awaiting_choice" and msg.text in ["🐉 Rồng", "⚖️ Hòa", "🐅 Hổ"])
async def choose_rongho(message: types.Message):
    user_id = str(message.from_user.id)
    choice_map = {"🐉 Rồng": "rong", "⚖️ Hòa": "hoa", "🐅 Hổ": "ho"}
    choice = choice_map[message.text]
    log_action(user_id, "Chọn cửa cược", choice)

    rongho_states[user_id] = {"choice": choice, "awaiting_bet": True}
    await message.answer("💰 Nhập số tiền cược (từ 1,000 VNĐ đến 10,000,000 VNĐ):", reply_markup=ReplyKeyboardRemove())

# ===================== 💰 ĐẶT CƯỢC =====================
@router.message(lambda msg: rongho_states.get(str(msg.from_user.id), {}).get("awaiting_bet") == True)
async def bet_rongho_amount(message: types.Message):
    user_id = str(message.from_user.id)
    bet_text = message.text.strip()

    if not bet_text.isdigit():
        await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ!")
        log_action(user_id, "Lỗi cược", "Số tiền không hợp lệ")
        return

    bet_amount = int(bet_text)
    log_action(user_id, "Đặt cược", f"{bet_amount:,} VNĐ")

    if bet_amount < 1000 or bet_amount > 10000000:
        await message.answer("⚠️ Số tiền cược phải từ 1,000 VNĐ đến 10,000,000 VNĐ!")
        log_action(user_id, "Lỗi cược", "Số tiền ngoài phạm vi hợp lệ")
        return

    state = rongho_states.get(user_id)
    if state is None:
        await message.answer("⚠️ Lỗi: Không tìm thấy trạng thái game!")
        log_action(user_id, "Lỗi game", "Không tìm thấy trạng thái")
        return

    if user_balance.get(user_id, 0) < bet_amount:
        await message.answer("❌ Số dư không đủ!")
        log_action(user_id, "Lỗi cược", "Số dư không đủ")
        rongho_states.pop(user_id, None)
        return

    # Trừ tiền cược và lưu lại dữ liệu
    user_balance[user_id] -= bet_amount
    save_data(data)
    await add_commission(user_id, bet_amount)
    
    # 🎲 Lật bài - Hiển thị hiệu ứng
    await message.answer("🔄 Đang chia bài...")
    await asyncio.sleep(3)

    # Chia bài cho Rồng & Hổ (ngẫu nhiên từ 1 đến 13)
    rong_card = random.randint(1, 13)
    ho_card = random.randint(1, 13)

    # Emoji bài tây tương ứng
    card_emoji = {1: "🂡", 2: "🂢", 3: "🂣", 4: "🂤", 5: "🂥", 6: "🂦", 7: "🂧", 8: "🂨", 9: "🂩", 10: "🂪", 11: "🂫", 12: "🂭", 13: "🂮"}
    rong_card_emoji = card_emoji[rong_card]
    ho_card_emoji = card_emoji[ho_card]

    # 🃏 Hiển thị bài của Rồng & Hổ
    await message.answer(f"🎴 Lật bài:\n🐉 Rồng: {rong_card} {rong_card_emoji}\n🐅 Hổ: {ho_card} {ho_card_emoji}")

    # 🔥 Xác định kết quả
    result = "rong" if rong_card > ho_card else "ho" if ho_card > rong_card else "hoa"
    chosen = state.get("choice")

    win_amount = 0
    outcome_text = ""

    if result == "hoa":
        if chosen == "hoa":
            win_amount = int(bet_amount * 7.98)
            user_balance[user_id] += win_amount
            save_data(data)
            outcome_text = (
                f"⚖️ Kết quả: Hòa!\n"
                f"🎉 Bạn thắng!\n"
                f"💰 Số tiền thắng: {win_amount:,} VNĐ\n"
                f"🏆 Chúc mừng bạn!"
            )
        else:
            outcome_text = (
                f"⚖️ Kết quả: Hòa!\n"
                f"😞 Bạn thua!\n"
                f"💸 Số tiền thua: {bet_amount:,} VNĐ"
            )
    else:
        result_text = "🐉 Rồng" if result == "rong" else "🐅 Hổ"
        if chosen == result:
            win_amount = int(bet_amount * 1.98)
            user_balance[user_id] += win_amount
            save_data(data)
            outcome_text = (
                f"🎲 Kết quả: {result_text} thắng!\n"
                f"🎉 Bạn thắng!\n"
                f"💰 Số tiền thắng: {win_amount:,} VNĐ\n"
                f"🏆 Chúc mừng bạn!"
            )
        else:
            outcome_text = (
                f"🎲 Kết quả: {result_text} thắng!\n"
                f"😞 Bạn thua!\n"
                f"💸 Số tiền thua: {bet_amount:,} VNĐ"
            )

    log_action(user_id, "Kết quả", f"Kết quả: {result}, Người chọn: {chosen}, {outcome_text}")
    await message.answer(outcome_text)

    # 📜 Lưu lịch sử cược
    record_bet_history(user_id, "Rồng Hổ", bet_amount, f"{result} - {'win' if win_amount > 0 else 'lose'}", win_amount)

    rongho_states.pop(user_id, None)
    log_action(user_id, "Kết thúc game", "Đã xóa trạng thái game")
    
# ===================== GAME: Đào Vàng (Mines Gold style) =====================
@router.message(F.text == "⛏️ Đào Vàng")
async def start_daovang(message: types.Message):
    user_id = str(message.from_user.id)
    log_action(user_id, "Bắt đầu chơi ⛏️Đào Vàng", "Chờ nhập số tiền cược")
    await message.answer(
        f"Nhập số tiền cược (tối thiểu {MIN_BET} VNĐ):",
        reply_markup=ReplyKeyboardRemove()
    )
    daovang_states[user_id] = {"awaiting_bet": True}

@router.message(lambda msg: daovang_states.get(str(msg.from_user.id), {}).get("awaiting_bet") == True and msg.text.isdigit())
async def daovang_set_bet(message: types.Message):
    user_id = str(message.from_user.id)
    bet = int(message.text)
    log_action(user_id, "Đặt cược", f"{bet:,} VNĐ")

    if bet < MIN_BET:
        await message.answer(f"❌ Số tiền cược phải tối thiểu {MIN_BET} VNĐ. Vui lòng nhập lại:")
        log_action(user_id, "Lỗi cược", f"Số tiền dưới mức tối thiểu {MIN_BET} VNĐ")
        return
    if user_balance.get(user_id, 0) < bet:
        await message.answer("❌ Số dư không đủ!")
        log_action(user_id, "Lỗi cược", "Số dư không đủ")
        daovang_states.pop(user_id, None)
        return

    user_balance[user_id] -= bet
    data["balances"] = user_balance
    save_data(data)
    await add_commission(user_id, bet)
    
    daovang_states[user_id] = {
        "bet": bet,
        "awaiting_bomb_count": True
    }
    await message.answer(
        "Nhập số bom bạn muốn (từ 1 đến 24, mặc định là 3 nếu không hợp lệ):",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: daovang_states.get(str(msg.from_user.id), {}).get("awaiting_bomb_count") == True)
async def daovang_set_bomb_count(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text.strip()
    bomb_count = 3
    if text.isdigit():
        chosen = int(text)
        if 1 <= chosen <= 24:
            bomb_count = chosen
        else:
            await message.answer("Số bom không hợp lệ. Sử dụng mặc định: 3 bom.")
            log_action(user_id, "Số bom không hợp lệ", f"Chọn: {chosen}, Sử dụng mặc định: 3 bom")
    else:
        await message.answer("Không nhận dạng được số bom. Sử dụng mặc định: 3 bom.")
        log_action(user_id, "Số bom không hợp lệ", "Không nhận dạng được, Sử dụng mặc định: 3 bom")

    bomb_positions = random.sample(range(1, 26), bomb_count)
    daovang_states[user_id] = {
        "bet": daovang_states[user_id]["bet"],
        "bomb_count": bomb_count,
        "bomb_positions": bomb_positions,
        "chosen": set(),
        "active": True,
        "multiplier": 1.0
    }
    log_action(user_id, "Bắt đầu game", f"Số bom: {bomb_count}")
    await message.answer(
        f"Game Đào Vàng bắt đầu với {bomb_count} bom!\nChọn một ô từ 1 đến 25:",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: daovang_states.get(str(msg.from_user.id), {}).get("active") == True and msg.text.isdigit())
async def daovang_choose_cell(message: types.Message):
    user_id = str(message.from_user.id)
    cell = int(message.text)
    log_action(user_id, "Chọn ô", f"Ô: {cell}")

    if cell < 1 or cell > 25:
        await message.answer("❌ Vui lòng chọn một ô từ 1 đến 25!")
        log_action(user_id, "Lỗi chọn ô", "Ô ngoài phạm vi hợp lệ")
        return

    state = daovang_states[user_id]
    if cell in state["chosen"]:
        await message.answer(f"❌ Ô {cell} đã được chọn rồi, hãy chọn ô khác!")
        log_action(user_id, "Lỗi chọn ô", f"Ô {cell} đã được chọn")
        return

    if cell in state["bomb_positions"]:
        await message.answer("💣 Bạn đã chọn ô chứa BOM! Bạn mất hết tiền cược.")
        log_action(user_id, "Thua game", f"Chọn ô chứa bom: {cell}, Mất: {state['bet']:,} VNĐ")
        record_bet_history(user_id, "Đào Vàng", state["bet"], "bomb", 0)
        daovang_states.pop(user_id, None)
        return

    state["chosen"].add(cell)
    safe_count = len(state["chosen"])
    bomb_count = state["bomb_count"]
    current_multiplier = calculate_multiplier(safe_count, bomb_count)
    state["multiplier"] = current_multiplier
    win_amount = int(state["bet"] * current_multiplier)
    chosen_cells = sorted(list(state["chosen"]))
    chosen_str = ", ".join(str(x) for x in chosen_cells)
    total_safe = 25 - bomb_count

    log_action(user_id, "Chọn ô thành công", f"Ô: {cell}, Hệ số: x{current_multiplier:.2f}, Tiền thắng: {win_amount:,} VNĐ")

    if safe_count == total_safe:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Rút tiền đào vàng")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            f"Chọn ô {cell} thành công!\nHệ số thưởng hiện tại: x{current_multiplier:.2f}\n"
            f"Tiền thắng hiện tại: {win_amount} VNĐ.\n"
            f"Các ô đã chọn: {chosen_str}\n"
            "Bạn đã tìm được hết ô an toàn, vui lòng rút tiền.",
            reply_markup=keyboard
        )
    else:
        next_multiplier = calculate_multiplier(safe_count + 1, bomb_count)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Rút tiền đào vàng"), KeyboardButton(text="Chơi tiếp")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            f"Chọn ô {cell} thành công!\nHệ số thưởng hiện tại: x{current_multiplier:.2f}\n"
            f"Tiền thắng hiện tại: {win_amount} VNĐ.\n"
            f"Các ô đã chọn: {chosen_str}\n"
            f"Nếu chơi tiếp, hệ số sẽ tăng lên x{next_multiplier:.2f}.\n"
            "Bạn muốn 'Rút tiền đào vàng' hay 'Chơi tiếp'?",
            reply_markup=keyboard
        )

@router.message(F.text == "Rút tiền đào vàng")
async def daovang_withdraw(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in daovang_states or not daovang_states[user_id].get("active"):
        await message.answer("Bạn không có game Đào Vàng nào đang chạy!")
        log_action(user_id, "Lỗi rút tiền", "Không có game đang chạy")
        return

    state = daovang_states[user_id]
    win_amount = int(state["bet"] * state["multiplier"])
    user_balance[user_id] = user_balance.get(user_id, 0) + win_amount
    data["balances"] = user_balance
    save_data(data)

    log_action(user_id, "Rút tiền thành công", f"Nhận: {win_amount:,} VNĐ, Hệ số: x{state['multiplier']:.2f}")
    await message.answer(f"🎉 Bạn đã rút tiền thành công! Nhận {win_amount} VNĐ!", reply_markup=main_menu)
    record_bet_history(user_id, "Đào Vàng", state["bet"], "win", win_amount)
    daovang_states.pop(user_id, None)

@router.message(F.text == "Chơi tiếp")
async def daovang_continue(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in daovang_states or not daovang_states[user_id].get("active"):
        await message.answer("Bạn không có game Đào Vàng nào đang chạy!", reply_markup=main_menu)
        log_action(user_id, "Lỗi chơi tiếp", "Không có game đang chạy")
        return

    log_action(user_id, "Chơi tiếp", "Tiếp tục chọn ô")
    await message.answer(
        "Hãy chọn một ô từ 1 đến 25 (các ô đã chọn sẽ không được chọn lại):",
        reply_markup=ReplyKeyboardRemove()
    )

# ===================== GAME: Mini Poker =====================
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Giảm hệ số thưởng để game "khó ăn tiền" hơn
PRIZES = {
    "Thùng Phá Sảnh": 20,
    "Tứ Quý": 5,
    "Cù Lũ": 2.5,
    "Thùng": 1.8,
    "Sảnh": 1.5,
    "Đôi": 1.3,
    "Mậu Thầu": 0
}

CARD_DECK = ["♠A", "♥K", "♦Q", "♣J", "♠10", "♥9", "♦8", "♣7", "♠6", "♥5", "♦4", "♣3", "♠2"]

def danh_gia_bo_bai(cards):
    values = [card[1:] for card in cards]  # Lấy giá trị (bỏ chất)
    suits = [card[0] for card in cards]    # Lấy chất
    value_counts = {value: values.count(value) for value in set(values)}

    if len(set(suits)) == 1 and sorted(values) == ["10", "J", "Q", "K", "A"]:
        return "Thùng Phá Sảnh"
    if 4 in value_counts.values():
        return "Tứ Quý"
    if sorted(value_counts.values()) == [2, 3]:
        return "Cù Lũ"
    if len(set(suits)) == 1:
        return "Thùng"
    if sorted(values) == ["10", "J", "Q", "K", "A"]:
        return "Sảnh"
    if list(value_counts.values()).count(2) >= 1:
        return "Đôi"
    return "Mậu Thầu"

@router.message(F.text == "🃏 Mini Poker")
async def start_minipoker(message: types.Message):
    user_id = str(message.from_user.id)
    log_action(user_id, "Bắt đầu chơi 🃏 Mini Poker", "Chờ nhập số tiền cược")
    poker_states[user_id] = {"awaiting_bet": True}
    await message.answer(
        "💰 Nhập số tiền cược Mini Poker:",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: poker_states.get(str(msg.from_user.id), {}).get("awaiting_bet") == True and msg.text.isdigit())
async def play_minipoker(message: types.Message):
    user_id = str(message.from_user.id)
    bet = int(message.text)
    log_action(user_id, "Đặt cược", f"{bet:,} VNĐ")

    # Kiểm tra số dư
    if user_balance.get(user_id, 0) < bet:
        await message.answer("❌ Số dư không đủ!")
        log_action(user_id, "Lỗi cược", "Số dư không đủ")
        poker_states.pop(user_id, None)
        return

    # Lưu số tiền cược vào trạng thái của game
    poker_states[user_id]["bet"] = bet

    # Trừ tiền cược và lưu dữ liệu
    user_balance[user_id] -= bet
    save_data(data)
    await add_commission(user_id, bet)
    
    # Rút bài
    cards = random.sample(CARD_DECK, 5)
    hand_type = danh_gia_bo_bai(cards)

    # Áp dụng house edge: 30% trường hợp nếu bài thắng sẽ ép về "Mậu Thầu"
    if hand_type != "Mậu Thầu" and random.random() < 0.3:
        hand_type = "Mậu Thầu"

    multiplier = PRIZES.get(hand_type, 0)
    win_amount = int(bet * multiplier)

    if win_amount > 0:
        user_balance[user_id] += win_amount
        save_data(data)

    result_text = (
        f"🃏 **Bài của bạn:** {' '.join(cards)}\n"
        f"🎯 **Kết quả:** {hand_type}\n"
    )
    if win_amount > 0:
        result_text += f"🎉 **Thắng:** {win_amount} VNĐ (x{multiplier})!"
    else:
        result_text += "😢 **Chúc may mắn lần sau!**"

    log_action(user_id, "Kết quả", f"Bài: {' '.join(cards)}, Kết quả: {hand_type}, {'Thắng: ' + str(win_amount) + ' VNĐ' if win_amount > 0 else 'Thua'}")

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🃏 Chơi lại", callback_data="poker_replay")
    keyboard.button(text="🔙 Quay lại", callback_data="poker_back")

    await message.answer(result_text, reply_markup=keyboard.as_markup())
    record_bet_history(user_id, "Mini Poker", bet, f"{hand_type} - {'win' if win_amount > 0 else 'lose'}", win_amount)
    poker_states.pop(user_id, None)

@router.callback_query(lambda c: c.data == "poker_replay")
async def poker_replay(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    log_action(user_id, "Chơi lại", "Người chơi bấm 'Chơi lại'")
    await callback.message.delete()
    poker_states[user_id] = {"awaiting_bet": True, "bet": 0}
    await bot.send_message(user_id, "💰 Nhập số tiền cược Mini Poker:", reply_markup=ReplyKeyboardRemove())

@router.callback_query(lambda c: c.data == "poker_back")
async def poker_back(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    log_action(user_id, "Quay lại", "Người chơi bấm 'Quay lại'")
    await callback.message.delete()
    await bot.send_message(callback.from_user.id, "🔙 Quay lại menu chính.",reply_markup=main_menu)
    
# ===================== Nạp tiền =====================
import time
import pytz
from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command

deposit_states = {}
deposit_records = {}
user_balance = {}

def get_vietnam_time():
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(vn_tz).strftime('%Y-%m-%d %H:%M:%S')

def add_deposit_record(user_id, amount):
    """ Lưu lịch sử nạp tiền của người dùng """
    user_id = str(user_id)
    if user_id not in deposit_records:
        deposit_records[user_id] = []
    deposit_records[user_id].append({"time": get_vietnam_time(), "amount": amount})

@router.message(F.text == "🏧 Nạp tiền")
async def start_deposit(message: types.Message):
    user_id = str(message.from_user.id)
    deposit_states[user_id] = "awaiting_amount"

    deposit_info = (
        "💰 Để nạp tiền, vui lòng chuyển khoản đến:\n\n"
        "🏦 Ngân hàng:BIDV\n"
        "🏧 Số tài khoản:<pre>8894605025</pre>\n"
        "👤 Chủ tài khoản:LE PHUONG THAO\n"
        f"📌 Nội dung chuyển khoản:<pre>NAPTK {user_id}</pre>khi bạn bấm sẽ tự động sao chép lại\n\n"
        "⚠️ Số tiền nạp tối thiểu: 50.000 VNĐ.\n"
        "💰 Sau khi chuyển khoản, vui lòng nhập số tiền bạn đã chuyển"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Quay lại", callback_data="back_to_menu")

    await message.answer(deposit_info, parse_mode="HTML", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    await callback.message.answer("🔙 Quay lại menu chính.", reply_markup=main_menu)
    await callback.answer()

@router.callback_query(F.data == "deposit_history")
async def deposit_history(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    history = deposit_records.get(user_id, [])

    if not history:
        await callback.message.answer("📭 Bạn chưa có lịch sử nạp tiền nào.")
        return

    history_text = "\n".join([f"📅 {h['time']}: +{h['amount']} VNĐ" for h in history])
    await callback.message.answer(f"📥 Lịch sử nạp tiền của bạn:\n{history_text}")
    await callback.answer()
    
# ===================== Xử lý ảnh biên lai nạp tiền =====================
@router.message(F.photo)
async def deposit_photo_handler(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id == str(ADMIN_ID):
        return
    if deposit_states.get(user_id) == "awaiting_slip":
        if user_id not in deposits or not deposits[user_id]:
            await message.answer("Không tìm thấy yêu cầu nạp tiền của bạn. Vui lòng thử lại.")
            deposit_states[user_id] = None
            return
        for d_req in reversed(deposits[user_id]):
            if d_req["status"] == "pending" and d_req["photo_id"] is None:
                d_req["photo_id"] = message.photo[-1].file_id
                save_data(data)
                await bot.send_photo(ADMIN_ID, d_req["photo_id"], caption=(f"📢 User {user_id} yêu cầu nạp tiền:\n - Số tiền: {d_req['amount']} VNĐ\nVui lòng kiểm tra và xác nhận."))
                await message.answer(f"🎉 Bạn đã yêu cầu nạp {d_req['amount']} VNĐ. Vui lòng chờ admin xử lý.", reply_markup=main_menu)
                deposit_states[user_id] = None
                return
        await message.answer("Hiện không có yêu cầu nạp tiền nào đang chờ.")
        deposit_states[user_id] = None
    else:
        return

# ===================== Xử lý tin nhắn số (cho nạp tiền) =====================
@router.message(lambda msg: msg.text.isdigit())
async def handle_digit_message(message: types.Message):
    user_id = str(message.from_user.id)
    amount = int(message.text)
    if deposit_states.get(user_id) == "awaiting_amount":
        if user_id not in deposits:
            deposits[user_id] = []
        deposit_req = {
            "amount": amount,
            "photo_id": None,
            "status": "pending",
            "time": datetime.now().isoformat()
        }
        deposits[user_id].append(deposit_req)
        save_data(data)
        deposit_states[user_id] = "awaiting_slip"
        await message.answer(f"Bạn muốn nạp {amount} VNĐ.\nVui lòng gửi ảnh biên lai nạp tiền.")
        return

# ===================== Admin: Duyệt nạp tiền =====================
@router.message(Command("naptien"))
async def admin_confirm_deposit(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ Bạn không có quyền thực hiện hành động này.")
        return
    try:
        parts = message.text.split()
        user_id = parts[1]
        if user_id not in deposits or not deposits[user_id]:
            await message.answer("Không tìm thấy yêu cầu nạp tiền của user này.")
            return
        for d_req in deposits[user_id]:
            if d_req["status"] == "pending":
                d_req["status"] = "completed"
                amt = d_req["amount"]
                if user_id not in user_balance:
                    user_balance[user_id] = 0
                user_balance[user_id] += amt
                add_deposit_record(user_id, amt)  # ✅ Lưu lịch sử nạp tiền
                await bot.send_message(user_id, f"✅ Bạn đã được nạp {amt} VNĐ. Vui lòng kiểm tra số dư.")
                await message.answer(f"✅ Đã xác nhận nạp {amt} VNĐ cho user {user_id}.")
                return
        await message.answer("⚠️ Không có yêu cầu nạp tiền nào ở trạng thái chờ của user này.")
    except Exception as e:
        await message.answer("⚠️ Lỗi khi xác nhận nạp tiền. Cú pháp: /naptien <user_id>")
# ===================== Admin: Hủy yêu cầu nạp tiền =====================
@router.message(Command("huynaptien"))
async def admin_cancel_deposit(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ Bạn không có quyền thực hiện hành động này.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("⚠️ Cú pháp: /huynaptien <user_id> <index>")
            return

        user_id = parts[1]
        deposit_index = int(parts[2])

        # Lọc ra các giao dịch chưa được duyệt
        pending_deposits = [d for d in deposits.get(user_id, []) if d["status"] == "pending"]
        
        if not pending_deposits:
            await message.answer("⚠️ Không có yêu cầu nạp tiền nào ở trạng thái chờ của user này.")
            return

        if deposit_index < 1 or deposit_index > len(pending_deposits):
            await message.answer(f"⚠️ Chỉ có {len(pending_deposits)} yêu cầu, vui lòng chọn lại.")
            return

        # Lấy yêu cầu cần hủy theo index
        deposit_to_cancel = pending_deposits[deposit_index - 1]
        amount = deposit_to_cancel["amount"]

        # Xóa giao dịch khỏi danh sách
        deposits[user_id].remove(deposit_to_cancel)
        save_data(data)

        await bot.send_message(user_id, f"⚠️ Yêu cầu nạp {amount:,} VNĐ của bạn đã bị hủy bởi admin.")
        await message.answer(f"✅ Đã hủy yêu cầu nạp {amount:,} VNĐ của user {user_id}, yêu cầu thứ {deposit_index}.")

        logging.info(f"[Nạp tiền] Hủy yêu cầu nạp {amount:,} VNĐ của user {user_id}, yêu cầu thứ {deposit_index}.")

    except Exception as e:
        await message.answer("⚠️ Lỗi khi hủy yêu cầu nạp tiền. Cú pháp: /huynaptien <user_id> <index>")
        logging.error(f"Lỗi khi hủy yêu cầu nạp tiền: {e}")        
# ===================== Admin: Lệnh cộng tiền =====================
@router.message(Command("congtien"))
async def admin_add_money(message: types.Message):
    # Chỉ admin mới có quyền sử dụng lệnh này
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ Bạn không có quyền thực hiện hành động này.")
        return
    try:
        # Cú pháp: /congtien <user_id> <amount>
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("⚠️ Cú pháp: /congtien <user_id> <amount>")
            return
        
        target_user_id = parts[1]
        amount = int(parts[2])
        
        # Nếu user chưa có số dư, khởi tạo bằng 0
        if target_user_id not in user_balance:
            user_balance[target_user_id] = 0
        
        user_balance[target_user_id] += amount
        save_data(data)
        
        # Gửi thông báo đến người dùng được cộng tiền (nếu có)
        try:
            await bot.send_message(target_user_id, f"✅ Bạn đã được admin cộng {amount} VNĐ vào số dư.")
        except Exception as e:
            logging.error(f"Không thể gửi tin nhắn đến user {target_user_id}: {e}")
            
        await message.answer(f"✅ Đã cộng {amount} VNĐ cho user {target_user_id}.")
    except Exception as e:
        await message.answer("⚠️ Lỗi khi cộng tiền. Cú pháp: /congtien <user_id> <amount>")
        logging.error(f"Error in admin add money: {e}")

# ===================== Nút Rút tiền =====================
@router.message(F.text == "💸 Rút tiền")
async def start_withdraw(message: types.Message):
    withdraw_instruction = (
        "💸 Để rút tiền, vui lòng nhập thông tin theo mẫu sau:\n\n"
        "[Số tiền] [Họ tên] [Ngân hàng] [Số tài khoản]\n\n"
        "📝 Ví dụ: 1000000 NguyenVanA BIDV 1234567890\n\n"
        "⚠️ Lưu ý:\n"
        "- Số tiền phải nhỏ hơn hoặc bằng số dư hiện tại.\n"
        "- Số tiền rút tối thiểu là 200k.\n"
        "- Họ tên phải khớp với tên chủ tài khoản ngân hàng.\n"
        "- Sau khi kiểm tra, admin sẽ xử lý giao dịch."
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Quay lại", callback_data="back_to_menu")
    await message.answer(withdraw_instruction, reply_markup=kb.as_markup())
@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    await callback.message.answer("🔙 Quay lại menu chính.", reply_markup=main_menu)
    await callback.answer()

@router.callback_query(lambda c: c.data == "withdraw_history")
async def withdraw_history_handler(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    if user_id not in withdrawals or not withdrawals[user_id]:
        await callback.message.answer("📜 Bạn chưa có lịch sử rút tiền.", reply_markup=main_menu)
        await callback.answer()
        return

    history_list = withdrawals[user_id]
    text = "\n".join([
        f"⏰ {req.get('time', '?')}\n"
        f"💸 Số tiền: {req.get('amount', 0):,} VNĐ\n"
        f"🏦 Ngân hàng: {req.get('bank_name', 'N/A')}\n"
        f"👤 Người nhận: {req.get('full_name', 'N/A')}\n"
        f"🏧 Số tài khoản: {req.get('account_number', 'N/A')}\n"
        f"----------------------"
        for req in history_list
    ])
    
    await callback.message.answer(f"📜 *Lịch sử rút tiền của bạn:*\n{text}", parse_mode="Markdown")
    await callback.answer()


#               XỬ LÝ YÊU CẦU RÚT TIỀN CỦA NGƯỜI DÙNG
# ======================================================================
from datetime import datetime, timedelta

# Hàm lấy thời gian hiện tại theo giờ Việt Nam
def get_vietnam_time():
    return (datetime.utcnow() + timedelta(hours=7)).strftime("%d-%m-%Y %H:%M:%S")

@router.message(lambda msg: msg.from_user.id != ADMIN_ID 
                          and msg.text 
                          and len(msg.text.split()) >= 4 
                          and msg.text.split()[0].isdigit())
async def process_withdraw_request(message: types.Message):
    user_id = str(message.from_user.id)
    logging.info(f"[Yêu cầu Rút tiền] Nhận từ user {user_id}: {message.text}")

    parts = message.text.strip().split()
    try:
        amount = int(parts[0])
    except ValueError:
        await message.answer("⚠️ Số tiền không hợp lệ.", reply_markup=main_menu)
        return

    if amount < 200000:
        await message.answer("⚠️ Số tiền rút tối thiểu là 200.000 VNĐ. Vui lòng nhập lại.", reply_markup=main_menu)
        return

    if user_id not in user_balance:
        await message.answer("⚠️ Bạn chưa có tài khoản. Vui lòng dùng /start để tạo tài khoản.", reply_markup=main_menu)
        return

    if user_balance.get(user_id, 0) < amount:
        await message.answer("⚠️ Số dư không đủ để rút tiền.", reply_markup=main_menu)
        return

    full_name = parts[1]
    bank_name = parts[2]
    account_number = " ".join(parts[3:])  

    # Trừ số dư ngay lập tức
    user_balance[user_id] -= amount
    save_data(data)

    # Lưu thông tin rút tiền
    w_req = {
        "user_id": user_id,
        "amount": amount,
        "full_name": full_name,
        "bank_name": bank_name,
        "account_number": account_number,
        "status": "pending",
        "time": get_vietnam_time()
    }
    
    if user_id not in withdrawals or not isinstance(withdrawals[user_id], list):
        withdrawals[user_id] = []
    withdrawals[user_id].append(w_req)
    save_data(data)

    await bot.send_message(ADMIN_ID, (
        f"📢 *Yêu cầu rút tiền mới từ user {user_id}:*\n"
        f"💸 Số tiền: {amount:,} VNĐ\n"
        f"🏦 Ngân hàng: {bank_name}\n"
        f"👤 Người nhận: {full_name}\n"
        f"🏧 Số tài khoản: {account_number}\n"
        f"⏰ Thời gian: {w_req['time']}\n"
        "⚠️ Yêu cầu đang chờ xử lý."
    ), parse_mode="Markdown")

    await message.answer(
        f"✅ *Yêu cầu rút tiền {amount:,} VNĐ đã được gửi.*\n"
        f"⏰ *Thời gian:* {w_req['time']}\n"
        "💸 Số dư đã bị trừ và đang chờ admin xử lý.",
        parse_mode="Markdown",
        reply_markup=main_menu
    )

    await message.answer("Nếu quá 15p tiền chưa được cộng,💬 Bạn vui lòng nhắn tin cho hỗ trợ.", parse_mode="Markdown")

#           LỆNH ADMIN XÁC NHẬN XỬ LÝ YÊU CẦU RÚT TIỀN (/xacnhan)
# ======================================================================
@router.message(Command("xacnhan"))
async def admin_confirm_withdraw(message: types.Message):
    # Chỉ admin mới được phép dùng lệnh này
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ Bạn không có quyền thực hiện hành động này.")
        return
    try:
        # Cú pháp: /xacnhan <user_id> <số tiền>
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("⚠️ Cú pháp: /xacnhan <user_id> <số tiền>")
            return
        
        target_user_id = parts[1].strip()
        if not target_user_id:
            await message.answer("⚠️ ID người dùng không được để trống.")
            return
        if not target_user_id.isdigit():
            await message.answer("⚠️ Vui lòng nhập ID người dùng dưới dạng số.")
            return
        
        amount = int(parts[2])
        
        # Kiểm tra số tiền rút tối thiểu là 50.000 VNĐ
        if amount < 200000:
            await message.answer("⚠️ Số tiền rút tối thiểu là 200.000 VNĐ. Vui lòng nhập lại.")
            return

        # Tìm yêu cầu rút tiền của target_user_id với số tiền bằng amount và trạng thái "pending"
        if target_user_id not in withdrawals or not withdrawals[target_user_id]:
            await message.answer("Không tìm thấy yêu cầu rút tiền của user này.")
            return
        
        request_found = None
        for req in withdrawals[target_user_id]:
            if req["status"] == "pending" and req["amount"] == amount:
                request_found = req
                break
        
        if not request_found:
            await message.answer("Không tìm thấy yêu cầu rút tiền phù hợp.")
            return

        # Tại thời điểm này, số dư của user đã bị trừ khi họ gửi yêu cầu.
        # Xác nhận yêu cầu: cập nhật trạng thái thành "completed"
        request_found["status"] = "completed"
        save_data(data)
        
        # Nếu admin gửi kèm ảnh (biên lai), lấy file_id của ảnh có kích thước lớn nhất
        photo_id = None
        if message.photo:
            photo_id = message.photo[-1].file_id
        
        # Gửi thông báo cho người dùng: "Yêu cầu rút tiền <amount> VNĐ của bạn đã được xử lý. Vui lòng kiểm tra tài khoản."
        if photo_id:
            try:
                await bot.send_photo(
                    target_user_id,
                    photo=photo_id,
                    caption=f"✅ Yêu cầu rút tiền {amount} VNĐ của bạn đã được xử lý.\nVui lòng kiểm tra tài khoản."
                )
            except Exception as e:
                logging.error(f"Lỗi gửi ảnh đến user {target_user_id}: {e}")
                await bot.send_message(
                    target_user_id,
                    f"✅ Yêu cầu rút tiền {amount} VNĐ của bạn đã được xử lý.\nVui lòng kiểm tra tài khoản."
                )
        else:
            await bot.send_message(
                target_user_id,
                f"✅ Yêu cầu rút tiền {amount} VNĐ của bạn đã được xử lý.\nVui lòng kiểm tra tài khoản."
            )
        await message.answer(f"✅ Đã xác nhận xử lý yêu cầu rút tiền {amount} VNĐ cho user {target_user_id}.")
    except Exception as e:
        await message.answer("⚠️ Lỗi khi xử lý yêu cầu rút tiền. Cú pháp: /xacnhan <user_id> <số tiền>")
        logging.error(f"Lỗi xử lý rút tiền: {e}")
        
# ===================== Admin: Xem số dư =====================
# Dữ liệu game & tài khoản
user_balance = {}  # Lưu số dư người chơi
taixiu_states = {}
jackpot_states = {}
crash_states = {}
rongho_states = {}
daovang_states = {}
poker_states = {}

ADMIN_ID = 1985817060  

def get_game_status(uid: str):
    """ Kiểm tra người dùng đang chơi game gì """
    status = []

    if uid in taixiu_states and taixiu_states[uid]:
        status.append("Tài Xỉu")
    if uid in jackpot_states and jackpot_states[uid]:
        status.append("Jackpot")
    if uid in crash_states and crash_states[uid]:
        status.append("Máy Bay")
    if uid in rongho_states and rongho_states[uid]:
        status.append("Rồng Hổ")
    if uid in daovang_states and isinstance(daovang_states[uid], dict) and daovang_states[uid].get("active"):
        status.append("Đào Vàng")
    if uid in poker_states and poker_states[uid]:
        status.append("Mini Poker")

    return ", ".join(status) if status else "Không chơi"

@router.message(Command("tracuu"))
async def check_balance(message: types.Message):
    """ Xem danh sách người chơi, số dư và game đang chơi """
    try:
        if not user_balance:
            await message.answer("⚠️ Hiện chưa có người chơi nào có số dư.")
            return

        player_list = [
            f"{uid}: {user_balance.get(uid, 0)} VNĐ | {get_game_status(uid)}"
            for uid in user_balance.keys()
        ]
        
        response = "📊 Danh sách người chơi & số dư:\n" + "\n".join(player_list)
        await message.answer(response)

    except Exception as e:
        print(f"Lỗi khi lấy danh sách số dư: {str(e)}")
        await message.answer(f"⚠️ Lỗi khi lấy danh sách số dư: {str(e)}")

# ================== Khi người chơi tham gia game ==================
def player_join_game(user_id, game_name):
    """ Gọi khi người dùng tham gia bất kỳ game nào """
    user_id = str(user_id)
    
    # Cập nhật game mà user đang chơi
    if game_name == "Tài Xỉu":
        taixiu_states[user_id] = True
    elif game_name == "Jackpot":
        jackpot_states[user_id] = True
    elif game_name == "Máy Bay":
        crash_states[user_id] = True
    elif game_name == "Rồng Hổ":
        rongho_states[user_id] = True
    elif game_name == "Đào Vàng":
        daovang_states[user_id] = {"active": True}
    elif game_name == "Mini Poker":
        poker_states[user_id] = True

# ================== Khi người chơi thoát game ==================
def player_exit_game(user_id, game_name):
    """ Gọi khi người dùng rời khỏi một game """
    user_id = str(user_id)

    # Xóa trạng thái game của user
    if game_name == "Tài Xỉu":
        taixiu_states.pop(user_id, None)
    elif game_name == "Jackpot":
        jackpot_states.pop(user_id, None)
    elif game_name == "Máy Bay":
        crash_states.pop(user_id, None)
    elif game_name == "Rồng Hổ":
        rongho_states.pop(user_id, None)
    elif game_name == "Đào Vàng":
        daovang_states.pop(user_id, None)
    elif game_name == "Mini Poker":
        poker_states.pop(user_id, None)

import asyncio
import random
from aiogram import Router, types

# ===================== Quản lý số người chơi ảo =====================
game_players_default_range = {
    "🎲 Tài Xỉu": (42, 63),
    "🎰 Jackpot": (35, 49),
    "✈️ Máy Bay": (55, 87),
    "🐉 Rồng Hổ": (42, 61),
    "⛏️ Đào Vàng": (30, 42),
    "🃏 Mini Poker": (28, 38)
}

game_players = {game: random.randint(*game_players_default_range[game]) for game in game_players_default_range}
game_limits = {game: game_players_default_range[game] for game in game_players_default_range}  # Lưu min/max từng game

player_lock = False  # Nếu True, số người chơi không thay đổi
player_fixed_value = None  # Nếu không phải None, số người chơi cố định
last_update_time = 0  # Thời gian lần cuối cập nhật

async def update_players():
    """ Cập nhật số người chơi theo cơ chế tự nhiên. """
    print("✅ update_players() đã chạy!")  # Kiểm tra log
    while True:
        try:
            if not player_lock:
                for game in game_players:
                    delta = random.randint(-3, 3)
                    new_value = game_players[game] + delta
                    min_limit, max_limit = game_limits[game]  # Lấy min/max đã đặt
                    
                    # Nếu vượt quá giới hạn, điều chỉnh giảm dần
                    if new_value > max_limit:
                        game_players[game] -= random.randint(1, 4)  # Giảm từ từ
                    elif new_value < min_limit:
                        game_players[game] += random.randint(1, 4)  # Tăng từ từ
                    else:
                        game_players[game] = new_value  # Cập nhật bình thường

            elif player_fixed_value is not None:
                for game in game_players:
                    game_players[game] = player_fixed_value
                    
            await asyncio.sleep(7)  # Chờ 5 giây trước khi cập nhật tiếp
        except Exception as e:
            print(f"🔥 Lỗi trong update_players(): {e}")

import logging
from aiogram import types

logging.basicConfig(level=logging.INFO)

# ===================== Người dùng xem số người đang chơi =====================
@router.message(lambda msg: msg.text == "👥 Số người đang chơi")
async def show_players(message: types.Message):
    """ Hiển thị số người chơi hiện tại """
    logging.info(f"📌 Người dùng {message.from_user.id} bấm '👥 Số người đang chơi'.")

    try:
        player_text = "📊 Số người đang chơi mỗi game:\n\n"

        for game, count in game_players.items():
            player_text += f"{game}: {count} người chơi\n"
        
        player_text += "\n🔥 Hiện đang có rất nhiều người tham gia, hãy cùng chơi ngay và giành chiến thắng! 🎉"

        # Bổ sung nút cập nhật và quay lại
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🔄 Cập nhật")],
                [types.KeyboardButton(text="⬅ Quay lại")]
            ],
            resize_keyboard=True
        )

        await message.answer(player_text, reply_markup=keyboard)
        logging.info("✅ Gửi thành công danh sách số người đang chơi.")
    except Exception as e:
        logging.error(f"❌ Lỗi khi xử lý '👥 Số người đang chơi': {e}")

# ===================== Quay lại menu chính =====================
@router.message(lambda msg: msg.text == "⬅ Quay lại")
async def back_to_menu(message: types.Message):
    """ Xử lý khi người dùng bấm nút Quay lại """
    logging.info(f"📌 Người dùng {message.from_user.id} bấm '⬅ Quay lại'.")

    try:
        await message.answer("🏠 Bạn đã quay lại menu chính.", reply_markup=main_menu)
        logging.info("✅ Đã gửi tin nhắn quay lại menu chính.")
    except Exception as e:
        logging.error(f"❌ Lỗi khi xử lý '⬅ Quay lại': {e}")

# ===================== Người dùng cập nhật số người chơi =====================
@router.message(lambda msg: msg.text == "🔄 Cập nhật")
async def refresh_players(message: types.Message):
    """ Người dùng cập nhật số người chơi (không cho spam) """
    global last_update_time, game_players
    now = asyncio.get_event_loop().time()

    if now - last_update_time < 9:
        await message.answer("⏳ Vui lòng đợi 9 giây trước khi cập nhật lại!")
        return
    
    last_update_time = now  # Cập nhật thời gian cập nhật cuối cùng

    if not player_lock:  # Chỉ cập nhật nếu không bị khóa
        game_players = {game: random.randint(*game_limits[game]) for game in game_limits}

    await show_players(message)  # Hiển thị lại số người chơi mới

# ===================== Admin Tùy chỉnh số người chơi =====================
@router.message(lambda msg: msg.text.startswith("/setplayers "))
async def set_players(message: types.Message):
    """ Admin chỉnh số người chơi của game """
    global player_lock, player_fixed_value
    args = message.text.split()

    if len(args) != 4 or not args[2].isdigit() or not args[3].isdigit():
        await message.answer("⚠️ Cách dùng: `/setplayers [all/tên game] [min] [max]`\n🔹 VD: `/setplayers tài 50 80` hoặc `/setplayers all 40 90`", parse_mode="Markdown")
        return

    game_name = args[1].lower()
    min_value = int(args[2])
    max_value = int(args[3])

    if min_value < 20 or max_value > 200 or min_value >= max_value:
        await message.answer("⚠️ Số người chơi phải nằm trong khoảng từ 20 đến 200 và min phải nhỏ hơn max!", parse_mode="Markdown")
        return

    if game_name == "all":
        for game in game_players:
            game_limits[game] = (min_value, max_value)  # Lưu giới hạn mới
            game_players[game] = random.randint(min_value, max_value)
        await message.answer(f"🔒 Đã đặt số người chơi **tất cả game** trong khoảng {min_value} - {max_value} người.", parse_mode="Markdown")
    else:
        matched_games = [g for g in game_players if game_name in g.lower()]
        
        if not matched_games:
            await message.answer("⚠️ Không tìm thấy game nào với tên đó. Hãy thử lại!", parse_mode="Markdown")
            return

        for game in matched_games:
            game_limits[game] = (min_value, max_value)  # Lưu giới hạn mới
            game_players[game] = random.randint(min_value, max_value)

        game_list = "\n".join([f"🔹 {g}" for g in matched_games])
        await message.answer(f"🔒 Đã đặt số người chơi cho các game:\n{game_list}\n👉 Trong khoảng {min_value} - {max_value} người.", parse_mode="Markdown")
    
    player_lock = False  # Mở lại cập nhật tự động
    player_fixed_value = None  # Xóa giá trị cố định

@router.message(lambda msg: msg.text == "/unlockplayers")
async def unlock_players(message: types.Message):
    """ Admin mở khóa số người chơi (trở về random tự động) """
    global player_lock

    # Reset số người chơi về mặc định
    for game in game_players_default_range:
        game_limits[game] = game_players_default_range[game]  # Đặt lại giới hạn về mặc định
        game_players[game] = random.randint(*game_players_default_range[game])

    player_lock = False
    await message.answer("🔓 Đã mở khóa số người chơi, hệ thống sẽ tự động cập nhật.")
# ===================== Lệnh BAN người dùng =====================
@router.message(Command("ban"))
async def ban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Vui lòng nhập ID người dùng cần ban. Ví dụ: `/ban 123456789`", parse_mode="Markdown")
        return

    target_id = parts[1]
    if target_id in banned_users:
        await message.answer(f"⚠️ Người dùng `{target_id}` đã bị khóa trước đó.", parse_mode="Markdown")
        return

    banned_users.add(target_id)
    save_data(data)
    await message.answer(f"✅ Đã khóa tài khoản `{target_id}`.", parse_mode="Markdown")

@router.message(Command("unban"))
async def unban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Sai cú pháp! Dùng: `/unban user_id`", parse_mode="Markdown")
        return

    user_id = parts[1]
    if user_id in banned_users:
        banned_users.remove(user_id)
        await message.answer(f"✅ Đã mở khóa tài khoản {user_id}!")
        try:
            await bot.send_message(user_id, "✅ Tài khoản Mega6casino của bạn đã được mở lại", reply_markup=main_menu)
        except:
            pass
    else:
        await message.answer("⚠️ Người này không bị khóa!")

# ===================== Chạy bot =====================
async def main():
    # Chạy update_players() trong background
    asyncio.create_task(update_players())

    # Thiết lập các lệnh cho bot
    await bot.set_my_commands([
        BotCommand(command="start", description="Bắt đầu bot"),
        BotCommand(command="naptien", description="Admin duyệt nạp tiền"),
        BotCommand(command="xacnhan", description="Admin duyệt rút tiền"),
        BotCommand(command="congtien", description="Cộng tiền cho người dùng (Admin)"),
        BotCommand(command="tracuu", description="Xem người chơi (Admin)")
    ])

    # Bắt đầu bot với polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        # Khởi tạo event loop mới
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Chạy bot
        loop.run_until_complete(main())
    except RuntimeError as e:
        print(f"Error: {e}")
