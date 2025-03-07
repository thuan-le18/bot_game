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
    BotCommandScopeChat
)
from aiogram.filters import Command

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
        [KeyboardButton(text="🎮 Danh sách game")],
        [KeyboardButton(text="💰 Xem số dư"), KeyboardButton(text="📜 Lịch sử cược")],
        [KeyboardButton(text="🔄 Nạp tiền"), KeyboardButton(text="💸 Rút tiền")],
        [KeyboardButton(text="🎁 Hoa hồng"), KeyboardButton(text="🏆 VIP")]
    ],
    resize_keyboard=True
)

games_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎲 Tài Xỉu"), KeyboardButton(text="🎰 Jackpot")],
        [KeyboardButton(text="✈️ Máy Bay"), KeyboardButton(text="🐉 Rồng Hổ")],
        [KeyboardButton(text="⛏️ Đào Vàng"), KeyboardButton(text="🃏 Mini Poker")],
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
        BotCommand(command="admin_sodu", description="Xem số dư (Admin)"),
        BotCommand(command="naptien", description="Admin duyệt nạp tiền"),
        BotCommand(command="ruttien", description="Admin duyệt rút tiền"),
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
    new_user = False
    if user_id not in user_balance:
        user_balance[user_id] = NEW_USER_BONUS
        user_history[user_id] = []
        deposits[user_id] = []
        withdrawals[user_id] = []
        save_data(data)
        new_user = True
    deposit_states[user_id] = None
    jackpot_states[user_id] = False
    if new_user:
        await message.answer("👋 Chào mừng bạn đến với bot Tài Xỉu!\n(5k đã được cộng vào số dư)", reply_markup=main_menu)
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
    await message.answer(f"🏆 VIP của bạn: {current_vip}\nTổng nạp: {total_deposit} VNĐ", reply_markup=main_menu)

# ===================== Hoa Hồng Handler =====================
@router.message(F.text == "🎁 Hoa hồng")
async def referral_handler(message: types.Message):
    user_id = str(message.from_user.id)
    referral_link = f"https://t.me/your_bot?start={user_id}"
    # Xử lý mã giới thiệu nếu có. Giả sử khi người dùng gửi tin nhắn dạng: "🎁 Hoa hồng <referrer_id>"
    args = message.text.split()
    if len(args) > 1:
        referrer_id = args[1]
        # Kiểm tra xem không tự giới thiệu và chỉ nhận bonus một lần
        if referrer_id != user_id:
            if referrer_id not in referrals:
                referrals[referrer_id] = []
            if user_id not in referrals[referrer_id]:
                referrals[referrer_id].append(user_id)
                user_balance[referrer_id] = user_balance.get(referrer_id, 0) + 2000
                save_data(data)
                await bot.send_message(referrer_id, "🎉 Bạn vừa nhận 2.000 VNĐ vì mời được một người chơi mới!")
    
    await message.answer(f"🎁 Link mời của bạn: {referral_link}\nBạn nhận 2% hoa hồng từ số tiền cược của người được mời.", reply_markup=main_menu)

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
    await message.answer(f"💰 Số dư hiện tại của bạn: {balance} VNĐ", reply_markup=main_menu)

@router.message(F.text == "📜 Lịch sử cược")
async def bet_history(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Kiểm tra nếu không có dữ liệu lịch sử
    if user_id not in user_history or not user_history[user_id]:
        await message.answer("📜 Bạn chưa có lịch sử cược.", reply_markup=main_menu)
        return

    # Lấy danh sách lịch sử gần nhất (giới hạn 10 dòng để tránh quá dài)
    history_list = user_history[user_id][-10:]  

    text = "\n".join([
        f"⏰ {r.get('time', '?')}: {r.get('game', 'Unknown')} - Cược {r.get('bet_amount', 0):,} VNĐ\n"
        f"🔹 Kết quả: {r.get('result', r.get('random_number', '?'))} | "
        f"🏆 Thắng/Thua: {r.get('winnings', 0):,} VNĐ"
        for r in history_list
    ])

    await message.answer(f"📜 *Lịch sử cược gần đây của bạn:*\n{text}", reply_markup=main_menu, parse_mode="Markdown")

# ===================== GAME: Tài Xỉu =====================
@router.message(F.text == "🎲 Tài Xỉu")
async def start_taixiu(message: types.Message):
    user_id = str(message.from_user.id)
    taixiu_states[user_id] = "awaiting_choice"
    await message.answer(
        "Vui lòng chọn Tài hoặc Xỉu:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Tài"), KeyboardButton(text="Xỉu")]],
            resize_keyboard=True
        )
    )

@router.message(lambda msg: taixiu_states.get(str(msg.from_user.id)) == "awaiting_choice" and msg.text in ["Tài", "Xỉu"])
async def choose_taixiu(message: types.Message):
    user_id = str(message.from_user.id)
    taixiu_states[user_id] = {"choice": message.text, "state": "awaiting_bet"}
    await message.answer(f"Bạn đã chọn {message.text}. Vui lòng nhập số tiền cược:", reply_markup=ReplyKeyboardRemove())

@router.message(lambda msg: isinstance(taixiu_states.get(str(msg.from_user.id)), dict)
                          and taixiu_states[str(msg.from_user.id)].get("state") == "awaiting_bet"
                          and msg.text.isdigit())
async def play_taixiu(message: types.Message):
    user_id = str(message.from_user.id)
    bet_amount = int(message.text)
    if user_balance.get(user_id, 0) < bet_amount:
        await message.answer("❌ Số dư không đủ!")
        taixiu_states[user_id] = None
        return

    # Trừ tiền cược
    user_balance[user_id] -= bet_amount
    save_data(data)

    # Tung 3 quả xúc xắc với delay 2 giây mỗi lần
    dice_values = []
    for i in range(3):
        dice_msg = await message.answer_dice(emoji="🎲")
        dice_values.append(dice_msg.dice.value)
        await asyncio.sleep(2)
    
    total = sum(dice_values)
    result = "Tài" if total >= 11 else "Xỉu"
    user_choice = taixiu_states[user_id]["choice"]

    if user_choice == result:
        win_amount = int(bet_amount * 1.98)
        user_balance[user_id] += win_amount
        save_data(data)
        await message.answer(
            f"🎉 Kết quả xúc xắc: {dice_values[0]}, {dice_values[1]}, {dice_values[2]}\n"
            f"✨ Tổng điểm: {total} ({result})\n"
            f"Bạn thắng {win_amount} VNĐ!",
            reply_markup=main_menu
        )
    else:
        await message.answer(
            f"💥 Kết quả xúc xắc: {dice_values[0]}, {dice_values[1]}, {dice_values[2]}\n"
            f"✨ Tổng điểm: {total} ({result})\n"
            f"Bạn thua {bet_amount} VNĐ!",
            reply_markup=main_menu
        )
    taixiu_states[user_id] = None

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
    await message.answer("🎰 Đang quay Jackpot...")
    await asyncio.sleep(2)
    if random.randint(1, 100) <= 10:
        win_amount = bet_amount * 10
        user_balance[user_id] += win_amount
        save_data(data)
        await message.answer(f"🎉 Chúc mừng! Bạn trúng Jackpot x10! Nhận {win_amount} VNĐ!", reply_markup=main_menu)
    else:
        await message.answer("😢 Rất tiếc, bạn không trúng Jackpot. Mất hết tiền cược.", reply_markup=main_menu)
    jackpot_states[user_id] = False

# --- GAME: Máy Bay (Crash Game) ---
crash_games = {}

@router.message(F.text == "✈️ Máy Bay")
async def start_crash(message: types.Message):
    user_id = str(message.from_user.id)
    crash_states[user_id] = True
    await message.answer(
        "💰 Nhập số tiền cược, bot sẽ khởi động máy bay!",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: crash_states.get(str(msg.from_user.id)) == True and msg.text.isdigit())
async def initiate_crash_game(message: types.Message):
    user_id = str(message.from_user.id)
    bet = int(message.text)
    if user_balance.get(user_id, 0) < bet:
        await message.answer("❌ Số dư không đủ!")
        crash_states[user_id] = False
        return
    # Trừ tiền cược
    user_balance[user_id] -= bet
    save_data(data)
    # Xác định điểm rơi ngẫu nhiên cho máy bay
    crash_point = round(random.uniform(1.1, 10.0), 2)
    # Tạo một asyncio.Event để lắng nghe yêu cầu rút tiền ngay
    withdraw_event = asyncio.Event()
    crash_games[user_id] = {
         "bet": bet,
         "current_multiplier": 1.0,
         "running": True,
         "crash_point": crash_point,
         "withdraw_event": withdraw_event
    }
    keyboard = ReplyKeyboardMarkup(
         keyboard=[[KeyboardButton(text="Rút tiền máy bay")]],
         resize_keyboard=True,
         one_time_keyboard=True
    )
    await message.answer(
         f"🚀 Máy bay đang cất cánh...\n✈️ Hệ số nhân: x1.00\nNhấn 'Rút tiền máy bay' để rút tiền ngay!",
         reply_markup=keyboard
    )
    # Vòng lặp cập nhật hệ số nhân
    while crash_games[user_id]["running"]:
         try:
             # Chờ 1 giây hoặc chờ sự kiện rút tiền, nếu có thì sẽ trả về ngay
             await asyncio.wait_for(crash_games[user_id]["withdraw_event"].wait(), timeout=1)
             # Nếu sự kiện được kích hoạt, xử lý rút tiền ngay
             if crash_games[user_id]["withdraw_event"].is_set():
                 win_amount = round(bet * crash_games[user_id]["current_multiplier"])
                 user_balance[user_id] += win_amount
                 save_data(data)
                 await message.answer(
                     f"🎉 Bạn đã rút tiền thành công! Nhận {win_amount} VNĐ!",
                     reply_markup=main_menu
                 )
                 crash_games[user_id]["running"] = False
                 break
         except asyncio.TimeoutError:
             # Nếu không có sự kiện rút tiền, cập nhật hệ số nhân sau 1 giây
             new_multiplier = round(crash_games[user_id]["current_multiplier"] + 0.2, 2)
             crash_games[user_id]["current_multiplier"] = new_multiplier
             if new_multiplier >= crash_games[user_id]["crash_point"]:
                  await message.answer(
                      f"💥 Máy bay rơi tại x{crash_games[user_id]['crash_point']}! Bạn thua {bet} VNĐ!",
                      reply_markup=main_menu
                  )
                  crash_games[user_id]["running"] = False
                  break
             await message.answer(f"✈️ Hệ số nhân: x{new_multiplier}")
    crash_states[user_id] = False
    if user_id in crash_games:
         del crash_games[user_id]

@router.message(F.text == "Rút tiền máy bay")
async def withdraw_crash(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id in crash_games and crash_games[user_id]["running"]:
         crash_games[user_id]["withdraw_event"].set()
         await message.answer("Đang xử lý rút tiền máy bay...", reply_markup=ReplyKeyboardRemove())

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)

# ===================== Handler bắt đầu game Rồng Hổ =====================
@router.message(F.text == "🐉 Rồng Hổ")
async def start_rongho(message: types.Message):
    user_id = str(message.from_user.id)
    logging.info(f"[start_rongho] Called for user {user_id}")
    
    # Tạo bàn phím inline cho người chơi chọn cửa cược
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
    
    # Lấy lựa chọn: "rong", "hoa" hoặc "ho"
    choice = parts[1]
    logging.info(f"[choose_rongho] User {user_id} chọn {choice}")
    
    # Lưu trạng thái cho người dùng
    rongho_states[user_id] = {"choice": choice, "awaiting_bet": True}
    
    # Yêu cầu nhập số tiền cược
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

    # Kiểm tra số dư
    if user_balance.get(user_id, 0) < bet_amount:
        await message.answer("❌ Số dư không đủ!")
        rongho_states.pop(user_id, None)
        return

    # Trừ tiền cược và lưu dữ liệu
    user_balance[user_id] -= bet_amount
    save_data(data)

    # Chọn kết quả ngẫu nhiên: "rong", "hoa", "ho"
    result = random.choice(["rong", "hoa", "ho"])
    chosen = state.get("choice")
    logging.info(f"[bet_rongho_amount] Kết quả: {result}, Người chọn: {chosen}")

    # Xử lý kết quả
    if result == "hoa":
        if chosen == "hoa":
            win_amount = int(bet_amount * 7)
            user_balance[user_id] += win_amount
            save_data(data)
            await message.answer(f"🎉 Kết quả: ⚖️ Hòa! Bạn thắng {win_amount} VNĐ!", reply_markup=main_menu)
        else:
            await message.answer(f"😢 Kết quả: ⚖️ Hòa! Bạn thua {bet_amount} VNĐ!", reply_markup=main_menu)
    else:
        if chosen == result:
            win_amount = int(bet_amount * 1.98)
            user_balance[user_id] += win_amount
            save_data(data)
            # Chuyển kết quả thành chữ đẹp hơn
            result_text = "Rồng" if result == "rong" else "Hổ"
            await message.answer(f"🎉 {result_text} thắng! Bạn thắng {win_amount} VNĐ!", reply_markup=main_menu)
        else:
            result_text = "Rồng" if result == "rong" else "Hổ"
            await message.answer(f"😢 Kết quả: {result_text}! Bạn thua {bet_amount} VNĐ!", reply_markup=main_menu)

    # Xóa trạng thái game của người dùng
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
        # Nếu đã tìm được hết ô an toàn, chỉ cho phép rút tiền
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

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
import random

# ===================== Cấu hình Mini Poker =====================
# Hệ số nhân thưởng cho các loại bài
PRIZES = {
    "Thùng Phá Sảnh": 10,  # Jackpot (cực hiếm)
    "Tứ Quý": 5,           # Thắng lớn
    "Cù Lũ": 3,            # Thắng vừa
    "Thùng": 2,            # Thắng nhỏ
    "Sảnh": 1.5,           # Thắng thấp
    "Đôi": 1.2,            # Thắng ít
    "Mậu Thầu": 0          # Không thắng
}

# Danh sách các lá bài
CARD_DECK = ["♠A", "♥K", "♦Q", "♣J", "♠10", "♥9", "♦8", "♣7", "♠6", "♥5", "♦4", "♣3", "♠2"]

# ===================== Hàm đánh giá bộ bài =====================
def danh_gia_bo_bai(cards):
    # Tách giá trị và chất của các lá bài
    values = [card[:-1] for card in cards]  # Bỏ ký tự cuối (chất)
    suits = [card[-1] for card in cards]    # Lấy ký tự cuối (chất)

    # Đếm số lần xuất hiện của mỗi giá trị
    value_counts = {value: values.count(value) for value in set(values)}

    # Kiểm tra Thùng Phá Sảnh
    if len(set(suits)) == 1 and sorted(values) == ["10", "J", "Q", "K", "A"]:
        return "Thùng Phá Sảnh"

    # Kiểm tra Tứ Quý
    if 4 in value_counts.values():
        return "Tứ Quý"

    # Kiểm tra Cù Lũ
    if sorted(value_counts.values()) == [2, 3]:
        return "Cù Lũ"

    # Kiểm tra Thùng
    if len(set(suits)) == 1:
        return "Thùng"

    # Kiểm tra Sảnh
    if sorted(values) == ["10", "J", "Q", "K", "A"]:
        return "Sảnh"

    # Kiểm tra Đôi
    if list(value_counts.values()).count(2) >= 1:
        return "Đôi"

    # Mậu Thầu (không có gì)
    return "Mậu Thầu"

# ===================== Handler bắt đầu game Mini Poker =====================
@router.message(F.text == "🃏 Mini Poker")
async def start_minipoker(message: types.Message):
    user_id = str(message.from_user.id)
    poker_states[user_id] = {"awaiting_bet": True}
    await message.answer(
        "💰 Nhập số tiền cược Mini Poker:",
        reply_markup=ReplyKeyboardRemove()
    )

# ===================== Handler xử lý cược và chơi game =====================
@router.message(lambda msg: poker_states.get(str(msg.from_user.id), {}).get("awaiting_bet") == True and msg.text.isdigit())
async def play_minipoker(message: types.Message):
    user_id = str(message.from_user.id)
    bet = int(message.text)

    # Kiểm tra số dư
    if user_balance.get(user_id, 0) < bet:
        await message.answer("❌ Số dư không đủ!")
        poker_states.pop(user_id, None)
        return
    
    # Trừ tiền cược
    user_balance[user_id] -= bet
    save_data(data)
    
    # Tạo bài ngẫu nhiên
    cards = random.sample(CARD_DECK, 5)
    hand_type = danh_gia_bo_bai(cards)
    multiplier = PRIZES.get(hand_type, 0)
    win_amount = int(bet * multiplier)
    
    # Cộng tiền thắng
    if win_amount > 0:
        user_balance[user_id] += win_amount
        save_data(data)
    
    # Tạo thông báo kết quả
    result_text = (
        f"🃏 **Bài của bạn:** {' '.join(cards)}\n"
        f"🎯 **Kết quả:** {hand_type}\n"
    )
    if win_amount > 0:
        result_text += f"🎉 **Thắng:** {win_amount} VNĐ (x{multiplier})!"
    else:
        result_text += "😢 **Chúc may mắn lần sau!**"

    # Tạo nút chơi lại
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🃏 Chơi lại", callback_data="poker_replay")
    keyboard.button(text="🔙 Quay lại", callback_data="poker_back")

    # Gửi kết quả
    await message.answer(result_text, reply_markup=keyboard.as_markup())
    poker_states.pop(user_id, None)

# ===================== Handler chơi lại =====================
@router.callback_query(lambda c: c.data == "poker_replay")
async def poker_replay(callback: types.CallbackQuery):
    await callback.message.delete()
    await start_minipoker(callback.message)

# ===================== Handler quay lại menu chính =====================
@router.callback_query(lambda c: c.data == "poker_back")
async def poker_back(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("🔙 Quay lại menu chính.", reply_markup=main_menu)
    
# ===================== Nạp tiền =====================
@router.message(F.text == "🔄 Nạp tiền")
async def start_deposit(message: types.Message):
    user_id = str(message.from_user.id)
    deposit_states[user_id] = "awaiting_amount"
    deposit_info = (
        "💰 Để nạp tiền, vui lòng chuyển khoản đến:\n\n"
        "🏦 Ngân hàng: BIDV\n"
        "📄 Số tài khoản: 8894605025\n"
        "👤 Chủ tài khoản: LE PHUONG THAO\n"
        f"📌 Nội dung chuyển khoản: NAPTK {user_id}\n\n"
        "Sau khi chuyển khoản, vui lòng nhập số tiền bạn đã chuyển:"
    )
    await message.answer(deposit_info, reply_markup=ReplyKeyboardRemove())

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
                save_data(data)
                await bot.send_message(user_id, f"✅ Bạn đã được nạp {amt} VNĐ. Vui lòng kiểm tra số dư.")
                await message.answer(f"✅ Đã xác nhận nạp {amt} VNĐ cho user {user_id}.")
                return
        await message.answer("⚠️ Không có yêu cầu nạp tiền nào ở trạng thái chờ của user này.")
    except Exception as e:
        await message.answer("⚠️ Lỗi khi xác nhận nạp tiền. Cú pháp: /naptien <user_id>")
        logging.error(f"Error confirming deposit: {e}")
# ===================== Admin: Lệnh cộng tiền =====================
@router.message(Command("naptien"))
async def admin_deposit(message: types.Message):
    # Chỉ admin mới có quyền sử dụng lệnh này
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ Bạn không có quyền thực hiện hành động này.")
        return
    try:
        # Cú pháp: /naptien user <user_id> <amount>
        parts = message.text.split()
        if len(parts) < 4 or parts[1].lower() != "user":
            await message.answer("⚠️ Cú pháp: /naptien user <user_id> <amount>")
            return
        target_user_id = parts[2]
        amount = int(parts[3])
        # Nếu user chưa có số dư, khởi tạo bằng 0
        if target_user_id not in user_balance:
            user_balance[target_user_id] = 0
        user_balance[target_user_id] += amount
        save_data(data)
        # Gửi thông báo đến user được cộng tiền
        await bot.send_message(target_user_id, f"✅ Bạn đã được admin cộng {amount} VNĐ vào số dư.")
        await message.answer(f"✅ Đã cộng {amount} VNĐ cho user {target_user_id}.")
    except Exception as e:
        await message.answer("⚠️ Lỗi khi cộng tiền. Cú pháp: /naptiennaptien user <user_id> <amount>")
        logging.error(f"Error in admin deposit: {e}")

# ===================== Nút Rút tiền =====================
@router.message(F.text == "💸 Rút tiền")
async def start_withdraw(message: types.Message):
    # Hướng dẫn người dùng nhập thông tin rút tiền theo mẫu:
    withdraw_instruction = (
        "💸 Để rút tiền, vui lòng nhập thông tin theo mẫu sau:\n\n"
        "[Số tiền] [Họ tên] [Ngân hàng] [Số tài khoản]\n\n"
        "📝 Ví dụ: 1000000 NguyenVanA BIDV 1234567890\n\n"
        "⚠️ Lưu ý:\n"
        "- Số tiền phải nhỏ hơn hoặc bằng số dư hiện tại.\n"
        "- Số tiền rút tối thiểu là 50k.\n"
        "- Họ tên phải khớp với tên chủ tài khoản ngân hàng.\n"
        "- Sau khi kiểm tra, admin sẽ xử lý giao dịch."
    )
    await message.answer(withdraw_instruction, reply_markup=ReplyKeyboardRemove())

#               XỬ LÝ YÊU CẦU RÚT TIỀN CỦA NGƯỜI DÙNG
# ======================================================================
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
    except Exception as e:
        await message.answer("⚠️ Số tiền không hợp lệ.", reply_markup=main_menu)
        return

    # Kiểm tra số tiền rút tối thiểu là 50.000 VNĐ
    if amount < 50000:
        await message.answer("⚠️ Số tiền rút tối thiểu là 50.000 VNĐ. Vui lòng nhập lại theo mẫu.", reply_markup=main_menu)
        return

    if user_id not in user_balance:
        await message.answer("⚠️ Bạn chưa có tài khoản. Vui lòng dùng /start để tạo tài khoản.", reply_markup=main_menu)
        return
    if user_balance.get(user_id, 0) < amount:
        await message.answer("⚠️ Số dư của bạn không đủ để rút tiền.", reply_markup=main_menu)
        return

    full_name = parts[1]
    bank_name = parts[2]
    account_number = " ".join(parts[3:])  # Cho phép số tài khoản có nhiều từ

    # Trừ số dư của người dùng ngay lập tức
    user_balance[user_id] -= amount
    save_data(data)
    
    # Tạo yêu cầu rút tiền với trạng thái "pending"
    w_req = {
        "user_id": user_id,
        "amount": amount,
        "full_name": full_name,
        "bank_name": bank_name,
        "account_number": account_number,
        "status": "pending",
        "time": datetime.now().isoformat()
    }
    if user_id not in withdrawals or not isinstance(withdrawals[user_id], list):
        withdrawals[user_id] = []
    withdrawals[user_id].append(w_req)
    save_data(data)
    
    # Gửi thông báo cho admin
    admin_message = (
        f"📢 Có yêu cầu rút tiền mới từ user {user_id}:\n"
        f" - Số tiền: {amount} VNĐ\n"
        f" - Họ tên: {full_name}\n"
        f" - Ngân hàng: {bank_name}\n"
        f" - Số tài khoản: {account_number}\n\n"
        "Yêu cầu của bạn đang chờ xử lý."
    )
    await bot.send_message(ADMIN_ID, admin_message)
    
    # Thông báo cho người dùng
    await message.answer(
        f"✅ Yêu cầu rút tiền {amount} VNĐ của bạn đã được gửi đến admin và đang chờ xử lý.\n"
        "Số dư của bạn đã bị trừ.",
        reply_markup=main_menu
    )
    
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
        if amount < 50000:
            await message.answer("⚠️ Số tiền rút tối thiểu là 50.000 VNĐ. Vui lòng nhập lại.")
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
@router.message(Command("admin_sodu"))
async def admin_check_balance(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    balances = "\n".join([f"ID {uid}: {amt} VNĐ" for uid, amt in user_balance.items()])
    await message.answer(f"📊 Số dư của tất cả người dùng:\n{balances}")

# ===================== Admin: Xem danh sách người chơi =====================
@router.message(Command("tracuu"))
async def admin_view_players(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    players_info = []
    for uid in user_balance.keys():
        info = f"User {uid}: Số dư: {user_balance.get(uid, 0)} VNĐ"
        if uid in current_bets:
            info += f", đang chơi Tài Xỉu (cược {current_bets[uid]['choice']})"
        if uid in jackpot_states and jackpot_states[uid]:
            info += ", đang chơi Jackpot"
        # Bạn có thể mở rộng cho các game khác nếu cần
        players_info.append(info)
    result = "\n".join(players_info)
    await message.answer(f"🕵️ Danh sách người chơi:\n{result}")

# ===================== Chạy bot =====================
async def main():
    await bot.set_my_commands([
        BotCommand(command="start", description="Bắt đầu bot"),
        BotCommand(command="naptien", description="Admin duyệt nạp tiền"),
        BotCommand(command="xacnhan", description="Admin duyệt rút tiền"),
        BotCommand(command="admin_sodu", description="Xem số dư tất cả user (Admin)"),
        BotCommand(command="tracuu", description="Xem người chơi (Admin)")
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

