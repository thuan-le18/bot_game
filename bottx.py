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
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {
            "balances": {},
            "history": {},
            "deposits": {},
            "withdrawals": {},
            "referrals": {},    # Thêm key cho referrals
            "current_id": 1
        }
    for key in ["balances", "history", "deposits", "withdrawals", "referrals"]:
        if key not in data:
            data[key] = {}  # Khởi tạo rỗng cho các key nếu chưa có
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
user_balance = data["balances"]
user_history = data["history"]
deposits = data["deposits"]
withdrawals = data["withdrawals"]
referrals = data["referrals"]
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

    commission = int(bet_amount * 0.02)
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
    await set_bot_commands(user_id)
    # Kiểm tra tham số referral từ deep link, ví dụ: "/start 123456789"
    parts = message.text.split()
    referrer_id = parts[1] if len(parts) > 1 else None

    new_user = False
    if user_id not in user_balance:
        user_balance[user_id] = NEW_USER_BONUS
        user_history[user_id] = []
        deposits[user_id] = []
        withdrawals[user_id] = []
        save_data(data)
        new_user = True

        # Nếu có referral và người giới thiệu hợp lệ, cộng bonus 2k cho người giới thiệu
        if referrer_id and referrer_id != user_id:
            if referrer_id not in referrals:
                referrals[referrer_id] = []
            if user_id not in [ref.get("user_id") for ref in referrals[referrer_id]]:
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

    deposit_states[user_id] = None
    jackpot_states[user_id] = False

    # Sửa lỗi thụt lề cho if new_user:
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
        await message.answer(welcome_text, reply_markup=main_menu, parse_mode="Markdown")
    else:
        await message.answer("👋 Chào mừng bạn quay lại!", reply_markup=main_menu)

# ===================== VIP Handler =====================
@router.message(F.text == "🏆 VIP")
async def vip_info(message: types.Message):
    user_id = str(message.from_user.id)
    total_deposit = sum(deposit.get("amount", 0) for deposit in deposits.get(user_id, []))
    current_vip = "Chưa đạt VIP nào"
    
    for vip, req_amount in sorted(vip_levels.items(), key=lambda x: x[1]):
        if total_deposit >= req_amount:
            current_vip = vip

    await message.answer(
        f"🏆 VIP của bạn: {current_vip}\n"
        f"👥 ID tài khoản bạn: {user_id}\n"
        f"💰 Tổng nạp: {total_deposit} VNĐ",
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
         "💰 Bạn nhận 2000 VNĐ và 2% hoa hồng từ số tiền cược của người được mời.",
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
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="💸 Lịch sử rút", callback_data="withdraw_history")
    kb.button(text="📥 Lịch sử nạp", callback_data="deposit_history")
    kb.button(text="👥 Chuyển tiền", callback_data="transfer_money")
    kb.adjust(1)
    await message.answer(f"💰 Số dư hiện tại của bạn: {balance} VNĐ", reply_markup=kb.as_markup())

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
from aiogram import Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import asyncio

taixiu_states = {}
user_balance = {}  # Giả sử có hệ thống lưu số dư
data = {}  # Dữ liệu tổng hợp

MIN_BET = 1_000  # Cược tối thiểu 1,000 VNĐ
MAX_BET = 10_000_000  # Cược tối đa 10 triệu VNĐ
COMBO_MULTIPLIERS = {"triple": 30, "specific": 3}  # Tỷ lệ thưởng

@router.message(F.text == "/huy")
async def cancel_bet(message: types.Message):
    """Cho phép người chơi hủy ván cược nếu bị kẹt"""
    user_id = str(message.from_user.id)

    if user_id in taixiu_states:
        del taixiu_states[user_id]
        await message.answer("✅ Bạn đã hủy ván cược! Bây giờ bạn có thể đặt cược mới.")
    else:
        await message.answer("❌ Bạn không có ván cược nào đang chờ.")
        
@router.message(F.text == "🎲 Tài Xỉu")
async def start_taixiu(message: types.Message):
    user_id = str(message.from_user.id)

    # Chặn spam cược liên tục
    if user_id in taixiu_states:
        await message.answer("⏳ Bạn đang có một ván cược chưa hoàn tất. Nhập /huy để hủy cược trước khi chơi lại!")
        return
    
    taixiu_states[user_id] = "awaiting_choice"
    await message.answer(
        "🎲 Vui lòng chọn loại cược:\n"
        "- **Tài/Xỉu**: Thắng khi tổng điểm là Tài (11-18) hoặc Xỉu (3-10).\n"
        "- **Bộ Ba 🎲**: Chọn một số từ 1-6, nếu cả 3 viên xúc xắc ra số đó, bạn thắng **30x tiền cược**.\n"
        "- **Cược Số 🎯**: Chọn một số từ 1-6, nếu số đó xuất hiện trong kết quả, bạn thắng **3x tiền cược**.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Tài"), KeyboardButton(text="Xỉu")],
                [KeyboardButton(text="Bộ Ba 🎲"), KeyboardButton(text="Cược Số 🎯")]
            ],
            resize_keyboard=True
        )
    )

@router.message(lambda msg: taixiu_states.get(str(msg.from_user.id)) == "awaiting_choice" and msg.text in ["Tài", "Xỉu", "Bộ Ba 🎲", "Cược Số 🎯"])
async def choose_taixiu(message: types.Message):
    user_id = str(message.from_user.id)

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
    taixiu_states[user_id]["number"] = int(message.text)
    taixiu_states[user_id]["state"] = "awaiting_bet"

    bet_type = taixiu_states[user_id]["choice"]
    multiplier = 30 if bet_type == "Bộ Ba 🎲" else 3

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
    else:
        outcome_text = f"😢 Bạn thua {bet_amount:,} VNĐ!"

    # Gửi kết quả
    await message.answer(f"🎲 Kết quả: {dice_values}\n✨ Tổng: {total} ({result})\n{outcome_text}", reply_markup=main_menu)

    # Lưu lịch sử cược
    record_bet_history(user_id, "Tài Xỉu", bet_amount, f"{result} - {'win' if win_amount > 0 else 'lose'}", win_amount)

    # Xóa trạng thái cược
    del taixiu_states[user_id]

# ===================== GAME: Jackpot =====================
@router.message(F.text == "🎰 Jackpot")
async def jackpot_game(message: types.Message):
    user_id = str(message.from_user.id)
    jackpot_states[user_id] = True
    await message.answer(
        "💰 Nhập số tiền bạn muốn cược:",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: jackpot_states.get(str(msg.from_user.id)) == True and msg.text.isdigit())
async def jackpot_bet(message: types.Message):
    user_id = str(message.from_user.id)
    bet_amount = int(message.text)
    if user_balance.get(user_id, 0) < bet_amount:
        await message.answer("❌ Số dư không đủ!")
        jackpot_states[user_id] = False
        return
    user_balance[user_id] -= bet_amount
    save_data(data)
    await add_commission(user_id, bet_amount)
    await message.answer("🎰 Đang quay Jackpot...")
    await asyncio.sleep(2)
    win_amount = 0
    if random.randint(1, 100) <= 10:
        win_amount = bet_amount * 15
        user_balance[user_id] += win_amount
        save_data(data)
        await message.answer(f"🎉 Chúc mừng! Bạn trúng Jackpot x15! Nhận {win_amount} VNĐ!", reply_markup=main_menu)
        record_bet_history(user_id, "Jackpot", bet_amount, "win", win_amount)
    else:
        await message.answer("😢 Rất tiếc, bạn không trúng Jackpot. Mất hết tiền cược.", reply_markup=main_menu)
        record_bet_history(user_id, "Jackpot", bet_amount, "lose", 0)
    jackpot_states[user_id] = False

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
    crash_states[user_id] = True
    await message.answer(
         "💰 Nhập số tiền cược (tối thiểu 1.000 VNĐ), bot sẽ khởi động máy bay!",
         reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: crash_states.get(str(msg.from_user.id), False) and msg.text.isdigit())
async def initiate_crash_game(message: types.Message):
    user_id = str(message.from_user.id)
    bet = int(message.text)

    if bet < 1000 or bet > 10000000:
        await message.answer("❌ Cược hợp lệ từ 1.000 VNĐ tối đa đến 10.000.000 VNĐ!", reply_markup=main_menu)
        crash_states[user_id] = False
        return

    if user_balance.get(user_id, 0) < bet:
        await message.answer("❌ Số dư không đủ!", reply_markup=main_menu)
        crash_states[user_id] = False
        return

    # Trừ tiền cược
    user_balance[user_id] -= bet
    save_data(user_balance)
    await add_commission(user_id, bet)

    # Xác định crash_point ngẫu nhiên (1.1 - 15.0)
    crash_point = round(random.uniform(1.1, 15.0), 2)
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
    bet = crash_games[user_id]["bet"]  # Lấy bet từ crash_games để tránh lỗi

    countdown_time = random.choice([5, 7, 9, 12])
    countdown_message = await message.answer(
        f"⏳ Máy bay sẽ cất cánh trong {countdown_time} giây..."
    )

    for i in range(countdown_time, 0, -1):
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=countdown_message.message_id,
                text=f"⏳ Máy bay sẽ cất cánh trong {i} giây..."
            )
        except Exception as e:
            logging.error(f"Lỗi khi cập nhật tin nhắn đếm ngược: {e}")
        await asyncio.sleep(1)

    try:
        await message.bot.delete_message(
            chat_id=message.chat.id,
            message_id=countdown_message.message_id
        )
    except Exception as e:
        logging.error(f"Lỗi khi xóa tin nhắn đếm ngược: {e}")

   # Gửi tin nhắn status ban đầu với nút "💸 Rút tiền máy bay"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    crash_keyboard = InlineKeyboardMarkup(inline_keyboard=[
         [InlineKeyboardButton(text="💸 Rút tiền máy bay", callback_data="withdraw_crash")]
    ])
    sent_message = await message.answer(
         f"✈️ Máy bay đang cất cánh...\n📈 Hệ số nhân: x1.00",
         reply_markup=crash_keyboard
    )
    crash_games[user_id]["message_id"] = sent_message.message_id

    # Vòng lặp cập nhật hệ số nhân mượt mà
    while crash_games[user_id]["running"]:
        try:
            await asyncio.wait_for(crash_games[user_id]["withdraw_event"].wait(), timeout=1)
            if crash_games[user_id]["withdraw_event"].is_set():
                win_amount = round(bet * crash_games[user_id]["current_multiplier"])
                user_balance[user_id] += win_amount
                save_data(user_balance)
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=crash_games[user_id]["message_id"],
                        text=f"🎉 Bạn đã rút tiền thành công! Nhận {win_amount:,} VNĐ!",
                        reply_markup=main_menu
                    )
                except Exception as e:
                    logging.error(f"Lỗi khi cập nhật tin nhắn rút tiền: {e}")
                record_bet_history(user_id, "Máy Bay", bet, "win", win_amount)
                crash_games[user_id]["running"] = False
                break
        except asyncio.TimeoutError:
            current_multiplier = crash_games[user_id]["current_multiplier"]

            if current_multiplier < 2.0:
                increment = round(random.uniform(0.1, 0.15), 2)
            elif current_multiplier < 5.0:
                increment = round(random.uniform(0.2, 0.35), 2)
            else:
                increment = round(random.uniform(0.4, 0.5), 2)

            new_multiplier = round(current_multiplier + increment, 2)
            if new_multiplier > 15.0:
                new_multiplier = 15.0
            crash_games[user_id]["current_multiplier"] = new_multiplier

            if new_multiplier >= crash_games[user_id]["crash_point"]:
                loss_amount = bet
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=crash_games[user_id]["message_id"],
                        text=f"💥 <b>Máy bay rơi tại</b> x{crash_games[user_id]['crash_point']}!\n❌ Bạn đã mất {loss_amount:,} VNĐ!",
                        parse_mode="HTML",
                        reply_markup=None
                    )
                except Exception as e:
                    logging.error(f"Lỗi khi cập nhật tin nhắn thua: {e}")
                record_bet_history(user_id, "Máy Bay", bet, "lose", 0)
                break

            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=crash_games[user_id]["message_id"],
                    text=f"✈️ Máy bay đang bay...\n📈 Hệ số nhân: x{new_multiplier}",
                    reply_markup=crash_keyboard
                )
            except Exception as e:
                logging.error(f"Lỗi khi cập nhật hệ số nhân: {e}")

    crash_states[user_id] = False
    crash_games.pop(user_id, None)
    await message.answer("🏠 Quay về menu chính.", reply_markup=main_menu)
    
@router.callback_query(lambda c: c.data == "withdraw_crash")
async def withdraw_crash(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    
    if user_id in crash_games and crash_games[user_id]["running"]:
        bet = crash_games[user_id]["bet"]
        multiplier = crash_games[user_id]["current_multiplier"]
        profit = round(bet * (multiplier - 1))  
        win_amount = profit + bet  

        user_balance[user_id] += win_amount
        save_data(user_balance)

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
    logging.info(f"[start_rongho] Called for user {user_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🐉 Rồng", callback_data="rongho_rong"),
            InlineKeyboardButton(text="⚖️ Hòa", callback_data="rongho_hoa"),
            InlineKeyboardButton(text="🐅 Hổ", callback_data="rongho_ho")
        ]
    ])
    await message.answer("🎲 Chọn cửa cược của bạn:", reply_markup=keyboard)

# ===================== Handler xử lý lựa chọn cửa cược =====================
@router.callback_query(lambda c: c.data.startswith("rongho_"))
async def choose_rongho(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    parts = callback_query.data.split("_")
    if len(parts) < 2:
        await callback_query.answer("Lỗi dữ liệu callback!")
        return
    choice = parts[1]
    logging.info(f"[choose_rongho] User {user_id} chọn {choice}")
    rongho_states[user_id] = {"choice": choice, "awaiting_bet": True}
    await callback_query.message.answer("💰 Nhập số tiền cược của bạn:")
    await callback_query.answer()

# ===================== Handler xử lý cược =====================
@router.message(lambda msg: rongho_states.get(str(msg.from_user.id), {}).get("awaiting_bet") == True 
                          and msg.text.strip().isdigit())
async def bet_rongho_amount(message: types.Message):
    user_id = str(message.from_user.id)
    bet_amount = int(message.text.strip())
    state = rongho_states.get(user_id)
    logging.info(f"[bet_rongho_amount] User {user_id} cược {bet_amount}, state={state}")

    if state is None:
        await message.answer("⚠️ Lỗi: Không tìm thấy trạng thái game!")
        return

    if user_balance.get(user_id, 0) < bet_amount:
        await message.answer("❌ Số dư không đủ!")
        rongho_states.pop(user_id, None)
        return

    # Trừ tiền cược và lưu lại dữ liệu
    user_balance[user_id] -= bet_amount
    save_data(data)
    await add_commission(user_id, bet_amount)

    # Lấy kết quả ngẫu nhiên từ bộ ba: "rong", "hoa", "ho"
    result = random.choice(["rong", "hoa", "ho"])
    chosen = state.get("choice")
    logging.info(f"[bet_rongho_amount] Kết quả: {result}, Người chọn: {chosen}")

    win_amount = 0
    outcome_text = ""

    if result == "hoa":
        if chosen == "hoa":
            win_amount = int(bet_amount * 7.98)
            user_balance[user_id] += win_amount
            save_data(data)
            outcome_text = f"⚖️ Hòa! Bạn thắng {win_amount} VNĐ!"
        else:
            outcome_text = f"⚖️ Hòa! Bạn thua {bet_amount} VNĐ!"
    else:
        if chosen == result:
            win_amount = int(bet_amount * 1.98)
            user_balance[user_id] += win_amount
            save_data(data)
            result_text = "Rồng" if result == "rong" else "Hổ"
            outcome_text = f"{result_text} thắng! Bạn thắng {win_amount} VNĐ!"
        else:
            result_text = "Rồng" if result == "rong" else "Hổ"
            outcome_text = f"{result_text}! Bạn thua {bet_amount} VNĐ!"

    await message.answer(f"🎉 Kết quả: {outcome_text}", reply_markup=main_menu)
    
    # Lưu lịch sử cược cho game Rồng Hổ
    record_bet_history(user_id, "Rồng Hổ", bet_amount, f"{result} - {'win' if win_amount > 0 else 'lose'}", win_amount)
    
    rongho_states.pop(user_id, None)
    logging.info(f"[bet_rongho_amount] Đã xóa trạng thái game của user {user_id}")
    
# ===================== GAME: Đào Vàng (Mines Gold style) =====================
@router.message(F.text == "⛏️ Đào Vàng")
async def start_daovang(message: types.Message):
    user_id = str(message.from_user.id)
    await message.answer(
        f"Nhập số tiền cược (tối thiểu {MIN_BET} VNĐ):",
        reply_markup=ReplyKeyboardRemove()
    )
    daovang_states[user_id] = {"awaiting_bet": True}

@router.message(lambda msg: daovang_states.get(str(msg.from_user.id), {}).get("awaiting_bet") == True and msg.text.isdigit())
async def daovang_set_bet(message: types.Message):
    user_id = str(message.from_user.id)
    bet = int(message.text)
    if bet < MIN_BET:
        await message.answer(f"❌ Số tiền cược phải tối thiểu {MIN_BET} VNĐ. Vui lòng nhập lại:")
        return
    if user_balance.get(user_id, 0) < bet:
        await message.answer("❌ Số dư không đủ!")
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
    else:
        await message.answer("Không nhận dạng được số bom. Sử dụng mặc định: 3 bom.")
    bomb_positions = random.sample(range(1, 26), bomb_count)
    daovang_states[user_id] = {
        "bet": daovang_states[user_id]["bet"],
        "bomb_count": bomb_count,
        "bomb_positions": bomb_positions,
        "chosen": set(),
        "active": True,
        "multiplier": 1.0
    }
    await message.answer(
        f"Game Đào Vàng bắt đầu với {bomb_count} bom!\nChọn một ô từ 1 đến 25:",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: daovang_states.get(str(msg.from_user.id), {}).get("active") == True and msg.text.isdigit())
async def daovang_choose_cell(message: types.Message):
    user_id = str(message.from_user.id)
    cell = int(message.text)
    if cell < 1 or cell > 25:
        await message.answer("❌ Vui lòng chọn một ô từ 1 đến 25!")
        return
    state = daovang_states[user_id]
    if cell in state["chosen"]:
        await message.answer(f"❌ Ô {cell} đã được chọn rồi, hãy chọn ô khác!")
        return
    if cell in state["bomb_positions"]:
        await message.answer("💣 Bạn đã chọn ô chứa BOM! Bạn mất hết tiền cược.", reply_markup=main_menu)
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
        await message.answer("Bạn không có game Đào Vàng nào đang chạy!", reply_markup=main_menu)
        return
    state = daovang_states[user_id]
    win_amount = int(state["bet"] * state["multiplier"])
    user_balance[user_id] = user_balance.get(user_id, 0) + win_amount
    data["balances"] = user_balance
    save_data(data)
    await message.answer(f"🎉 Bạn đã rút tiền thành công! Nhận {win_amount} VNĐ!", reply_markup=main_menu)
    record_bet_history(user_id, "Đào Vàng", state["bet"], "win", win_amount)
    daovang_states.pop(user_id, None)

@router.message(F.text == "Chơi tiếp")
async def daovang_continue(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in daovang_states or not daovang_states[user_id].get("active"):
        await message.answer("Bạn không có game Đào Vàng nào đang chạy!", reply_markup=main_menu)
        return
    await message.answer(
        "Hãy chọn một ô từ 1 đến 25 (các ô đã chọn sẽ không được chọn lại):",
        reply_markup=ReplyKeyboardRemove()
    )

# ===================== GAME: Mini Poker =====================
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
    values = [card[:-1] for card in cards]
    suits = [card[-1] for card in cards]
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
    poker_states[user_id] = {"awaiting_bet": True}
    await message.answer(
        "💰 Nhập số tiền cược Mini Poker:",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: poker_states.get(str(msg.from_user.id), {}).get("awaiting_bet") == True and msg.text.isdigit())
async def play_minipoker(message: types.Message):
    user_id = str(message.from_user.id)
    bet = int(message.text)

    # Kiểm tra số dư
    if user_balance.get(user_id, 0) < bet:
        await message.answer("❌ Số dư không đủ!")
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

    from aiogram.utils.keyboard import InlineKeyboardBuilder  # Đảm bảo import đúng chỗ
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🃏 Chơi lại", callback_data="poker_replay")
    keyboard.button(text="🔙 Quay lại", callback_data="poker_back")

    await message.answer(result_text, reply_markup=keyboard.as_markup())
    record_bet_history(user_id, "Mini Poker", bet, f"{hand_type} - {'win' if win_amount > 0 else 'lose'}", win_amount)
    poker_states.pop(user_id, None)

@router.callback_query(lambda c: c.data == "poker_replay")
async def poker_replay(callback: types.CallbackQuery):
    await callback.message.delete()
    user_id = str(callback.from_user.id)
    # Khởi tạo lại trạng thái mini poker, lưu bet = 0 để đảm bảo nếu dùng trong forceall
    poker_states[user_id] = {"awaiting_bet": True, "bet": 0}
    await bot.send_message(user_id, "💰 Nhập số tiền cược Mini Poker:", reply_markup=ReplyKeyboardRemove())

@router.callback_query(lambda c: c.data == "poker_back")
async def poker_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await bot.send_message(callback.from_user.id, "🔙 Quay lại menu chính.", reply_markup=main_menu)
    
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

    await message.answer("Nếu quá 5p tiền chưa được cộng,💬 Bạn vui lòng nhắn tin cho hỗ trợ.", parse_mode="Markdown")

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
    "🎲 Tài Xỉu": (32, 53),
    "🎰 Jackpot": (30, 37),
    "✈️ Máy Bay": (55, 82),
    "🐉 Rồng Hổ": (38, 52),
    "⛏️ Đào Vàng": (28, 45),
    "🃏 Mini Poker": (28, 40)
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
