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
TOKEN = "7586352892:AAFl26m48KYdNqiCR03wNlLmaPkXaccImfw"
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
            "current_id": 1
        }
    for key in ["balances", "history", "deposits", "withdrawals"]:
        if key not in data:
            data[key] = {}
    for uid in data["deposits"]:
        if not isinstance(data["deposits"][uid], list):
            data["deposits"][uid] = []
    for uid in data["withdrawals"]:
        if not isinstance(data["withdrawals"][uid], list):
            data["withdrawals"][uid] = []
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
user_balance = data["balances"]
user_history = data["history"]
deposits = data["deposits"]
withdrawals = data["withdrawals"]
current_id = data["current_id"]

# ===================== Các biến trạng thái =====================
deposit_states = {}       # user_id -> "awaiting_amount" / "awaiting_slip" / None
current_bets = {}         # user_id -> {"choice": "Tài" hoặc "Xỉu"}
jackpot_states = {}       # user_id -> True/False (đang chơi Jackpot)
# Các game khác có thể bổ sung state riêng nếu cần

# ===================== Hệ thống VIP & Bonus =====================
# VIP được điều chỉnh từ VIP 1 đến VIP 5
vip_levels = {
    "VIP 1": 100000,
    "VIP 2": 500000,
    "VIP 3": 1000000,
    "VIP 4": 5000000,
    "VIP 5": 10000000,
}
NEW_USER_BONUS = 5000  # Tặng 5k cho người mới

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
        [KeyboardButton(text="🥢 Xóc Đĩa"), KeyboardButton(text="⛏️ Đào Vàng")],
        [KeyboardButton(text="🃏 Mini Poker")],
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
        user_balance[user_id] = NEW_USER_BONUS=5000
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
    if user_id not in user_history or not user_history[user_id]:
        await message.answer("📜 Bạn chưa có lịch sử cược.", reply_markup=main_menu)
        return
    text = "\n".join([
        f"⏰ {r['time']}: {r.get('game','Unknown')} - Cược {r.get('bet_amount', 0)} VNĐ, "
        f"KQ: {r.get('result', r.get('random_number','?'))}, Thắng/Thua: {r['winnings']} VNĐ"
        for r in user_history[user_id]
    ])
    await message.answer(f"📜 Lịch sử cược của bạn:\n{text}", reply_markup=main_menu)

# ===================== Khai báo trạng thái cho từng game =====================
taixiu_states = {}    # Trạng thái game Tài Xỉu: có thể là "awaiting_choice" hoặc dict {"choice": ..., "state": "awaiting_bet"}
jackpot_states = {}   # Trạng thái game Jackpot: True khi đang chờ cược
crash_states = {}     # Trạng thái game Máy Bay (Crash): True khi đang chờ cược
rongho_states = {}    # Trạng thái game Rồng Hổ: True khi đang chờ cược
xocdia_states = {}    # Trạng thái game Xóc Đĩa: True khi đang chờ cược
gold_states = {}      # Trạng thái game Đào Vàng: True khi đang chờ nhập ô
poker_states = {}     # Trạng thái game Mini Poker: True khi đang chờ cược

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
    # Lưu lựa chọn và chuyển sang trạng thái chờ nhập cược
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
    user_balance[user_id] -= bet_amount
    save_data(data)
    # Giả lập kết quả game
    result = random.choice(["Tài", "Xỉu"])
    user_choice = taixiu_states[user_id]["choice"]
    if user_choice == result:
        win_amount = bet_amount * 2  # Ví dụ: nhân đôi số tiền cược khi thắng
        user_balance[user_id] += win_amount
        save_data(data)
        await message.answer(f"🎉 Kết quả: {result}. Bạn thắng {win_amount} VNĐ!", reply_markup=main_menu)
    else:
        await message.answer(f"💥 Kết quả: {result}. Bạn thua {bet_amount} VNĐ!", reply_markup=main_menu)
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
# Biến trạng thái cho game máy bay
crash_states = {}   # Đánh dấu trạng thái nhập cược
crash_games = {}    # Lưu trữ thông tin game theo user

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
    # Xác định điểm crash ngẫu nhiên
    crash_point = round(random.uniform(1.1, 10.0), 2)
    crash_games[user_id] = {
        "bet": bet,
        "current_multiplier": 1.0,
        "withdraw": False,
        "running": True,
        "crash_point": crash_point
    }
    # Gửi thông báo với nút "Rút tiền máy bay"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Rút tiền máy bay")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        f"🚀 Máy bay đang cất cánh...\n📈 Hệ số nhân: x1.00\nNhấn 'Rút tiền máy bay' để rút tiền ngay!",
        reply_markup=keyboard
    )
    # Vòng lặp tăng dần hệ số nhân
    while crash_games[user_id]["running"]:
        await asyncio.sleep(1)
        new_multiplier = round(crash_games[user_id]["current_multiplier"] + 0.3, 2)
        crash_games[user_id]["current_multiplier"] = new_multiplier
        # Nếu vượt điểm crash => thua hết tiền cược
        if new_multiplier >= crash_games[user_id]["crash_point"]:
            await message.answer(
                f"💥 Máy bay rơi tại x{crash_games[user_id]['crash_point']}! Bạn thua {bet} VNĐ!",
                reply_markup=main_menu
            )
            crash_games[user_id]["running"] = False
            break
        # Nếu người chơi đã nhấn "Rút tiền máy bay"
        if crash_games[user_id]["withdraw"]:
            win_amount = round(bet * new_multiplier)
            user_balance[user_id] += win_amount
            save_data(data)
            await message.answer(
                f"🎉 Bạn đã rút tiền thành công! Nhận {win_amount} VNĐ!",
                reply_markup=main_menu
            )
            crash_games[user_id]["running"] = False
            break
        await message.answer(f"📈 Hệ số nhân: x{new_multiplier}")
    crash_states[user_id] = False
    if user_id in crash_games:
        del crash_games[user_id]

@router.message(F.text == "Rút tiền máy bay")
async def withdraw_crash(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id in crash_games and crash_games[user_id]["running"]:
        crash_games[user_id]["withdraw"] = True
        await message.answer("Đang xử lý rút tiền máy bay...", reply_markup=ReplyKeyboardRemove())

# ===================== GAME: Rồng Hổ =====================
@router.message(F.text == "🐉🐅 Rồng Hổ")
async def start_rongho(message: types.Message):
    user_id = str(message.from_user.id)
    rongho_states[user_id] = True
    await message.answer(
        "🔹 Chọn cược: Rồng, Hổ hoặc Hòa\n💰 Nhập cược theo cú pháp: Rồng/Hổ/Hòa [số tiền]",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: rongho_states.get(str(msg.from_user.id)) == True 
                          and msg.text.lower().startswith(("rồng", "hổ", "hòa")))
async def bet_rongho(message: types.Message):
    user_id = str(message.from_user.id)
    bet = message.text.split()
    if len(bet) != 2 or not bet[1].isdigit():
        await message.answer("⚠️ Sai cú pháp! Nhập: Rồng/Hổ/Hòa [số tiền]")
        return

    choice, amount = bet[0].lower(), int(bet[1])
    result = random.choice(["rồng", "hổ", "hòa"])
    payout = amount * (7 if result == "hòa" else 1.96)

    if choice == result:
        await message.answer(f"🎉 Kết quả: {result.upper()}! Bạn thắng {payout} VNĐ!")
    else:
        await message.answer(f"😢 Kết quả: {result.upper()}! Bạn thua {amount} VNĐ!")
    rongho_states[user_id] = False  # Reset trạng thái

# ------------------- GAME: Xóc Đĩa (Đơn: Chẵn/Lẽ) -------------------
# Sử dụng biến trạng thái riêng cho game này
@router.message(F.text == "⚪🔴 Xóc Đĩa")
async def start_xocdia(message: types.Message):
    user_id = str(message.from_user.id)
    logging.debug(f"[XOC DIA] start_xocdia triggered for user {user_id}")
    xocdia_states[user_id] = "awaiting_choice"
    # Tạo bàn phím chỉ có 2 nút: Chẵn và Lẽ
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("Chẵn"), KeyboardButton("Lẽ")]],
        resize_keyboard=True
    )
    await message.answer("Chọn Chẵn hoặc Lẽ:", reply_markup=keyboard)

@router.message(lambda msg: xocdia_states.get(str(msg.from_user.id)) == "awaiting_choice" 
                          and msg.text.lower() in ["chẵn", "lẽ"])
async def choose_xocdia_side(message: types.Message):
    user_id = str(message.from_user.id)
    logging.debug(f"[XOC DIA] choose_xocdia_side received text: {message.text.lower()} for user {user_id}")
    # Lưu lựa chọn và chuyển sang bước nhập tiền cược
    xocdia_states[user_id] = {"choice": message.text.lower(), "state": "awaiting_bet"}
    await message.answer(f"Bạn đã chọn {message.text}. Vui lòng nhập số tiền cược:",
                         reply_markup=ReplyKeyboardRemove())

@router.message(lambda msg: isinstance(xocdia_states.get(str(msg.from_user.id)), dict)
                          and xocdia_states[str(msg.from_user.id)].get("state") == "awaiting_bet"
                          and msg.text.isdigit())
async def xocdia_bet(message: types.Message):
    user_id = str(message.from_user.id)
    bet_amount = int(message.text)

    # Kiểm tra số dư
    if user_balance.get(user_id, 0) < bet_amount:
        await message.answer("❌ Số dư không đủ!")
        xocdia_states[user_id] = None
        return

    # Trừ tiền cược
    user_balance[user_id] -= bet_amount
    save_data(data)

    # Quay kết quả: Tung 4 đồng xu, mỗi đồng xu là 0 (trắng) hoặc 1 (đỏ)
    # Nếu số đồng đỏ là 0, 2, hoặc 4 -> kết quả "chẵn", còn lại -> "lẽ"
    num_red = sum(random.choice([0, 1]) for _ in range(4))
    result = "chẵn" if num_red in [0, 2, 4] else "lẽ"
    outcome_desc = f"{4 - num_red} trắng - {num_red} đỏ"

    if xocdia_states[user_id]["choice"] == result:
        multiplier = 1.98
        win_amount = int(bet_amount * multiplier)
        user_balance[user_id] += win_amount
        save_data(data)
        await message.answer(f"Kết quả: {outcome_desc}\n🎉 Bạn thắng {win_amount} VNĐ!",
                             reply_markup=main_menu)
    else:
        await message.answer(f"Kết quả: {outcome_desc}\n😢 Bạn thua {bet_amount} VNĐ!",
                             reply_markup=main_menu)

    # Reset state
    xocdia_states[user_id] = None

# Hàm tính multiplier động dựa trên số ô an toàn (safe_count) và số bom (bomb_count)
def calculate_multiplier(safe_count, bomb_count):
    """
    Với bomb_count = 3, safe_count = 1 sẽ cho multiplier = 1 + 0.09 * 1^1.45 = 1.09.
    Các tham số:
      - k = 0.09 (điều chỉnh multiplier cho bomb_count = 3)
      - p = 1.45 (điều chỉnh tăng trưởng theo safe_count)
      - alpha = 0.114 (điều chỉnh giảm multiplier khi số bom tăng)
    Nếu số bom tăng, factor giảm để multiplier cho mỗi ô an toàn sẽ thấp hơn.
    """
    k = 0.09
    p = 1.45
    alpha = 0.114
    factor = k / (1 + alpha * max(bomb_count - 3, 0))
    return 1 + factor * (safe_count ** p)

# ------------------- GAME: Đào Vàng (Mines Gold style) -------------------
# Sử dụng biến daovang_states riêng cho game này
daovang_states = {}
MIN_BET = 1000  # Cược tối thiểu

# Bước 1: Khi người dùng bấm "⛏️ Đào Vàng", yêu cầu nhập tiền cược
@router.message(F.text == "⛏️ Đào Vàng")
async def start_daovang(message: types.Message):
    user_id = str(message.from_user.id)
    await message.answer(
        f"Nhập số tiền cược (tối thiểu {MIN_BET} VNĐ):",
        reply_markup=ReplyKeyboardRemove()
    )
    daovang_states[user_id] = {"awaiting_bet": True}

# Bước 2: Người dùng nhập tiền cược, sau đó yêu cầu nhập số bom muốn chơi
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
    # Trừ tiền cược và cập nhật số dư
    user_balance[user_id] -= bet
    data["balances"] = user_balance
    save_data(data)
    # Chuyển sang bước nhập số bom
    daovang_states[user_id] = {
        "bet": bet,
        "awaiting_bomb_count": True
    }
    await message.answer(
        "Nhập số bom bạn muốn (từ 1 đến 24, mặc định là 3 nếu không hợp lệ):",
        reply_markup=ReplyKeyboardRemove()
    )

# Bước 3: Nhận số bom và khởi tạo game với grid từ 1 đến 25
@router.message(lambda msg: daovang_states.get(str(msg.from_user.id), {}).get("awaiting_bomb_count") == True)
async def daovang_set_bomb_count(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text.strip()
    bomb_count = 3  # giá trị mặc định
    if text.isdigit():
        chosen = int(text)
        if 1 <= chosen <= 24:
            bomb_count = chosen
        else:
            await message.answer("Số bom không hợp lệ. Sử dụng mặc định: 3 bom.")
    else:
        await message.answer("Không nhận dạng được số bom. Sử dụng mặc định: 3 bom.")
    # Khởi tạo game: grid gồm 25 ô
    bomb_positions = random.sample(range(1, 26), bomb_count)
    daovang_states[user_id] = {
        "bet": daovang_states[user_id]["bet"],
        "bomb_count": bomb_count,
        "bomb_positions": bomb_positions,
        "chosen": set(),   # Các ô đã chọn an toàn
        "active": True,
        "multiplier": 1.0  # Ban đầu multiplier là 1.0
    }
    await message.answer(
        f"Game Đào Vàng bắt đầu với {bomb_count} bom!\nChọn một ô từ 1 đến 25:",
        reply_markup=ReplyKeyboardRemove()
    )

# Bước 4: Người dùng chọn ô; nếu an toàn, cập nhật số ô an toàn và multiplier
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
    # Nếu chọn ô chứa bom -> game kết thúc (thua cược)
    if cell in state["bomb_positions"]:
        await message.answer("💣 Bạn đã chọn ô chứa BOM! Bạn mất hết tiền cược.", reply_markup=main_menu)
        daovang_states.pop(user_id, None)
        return
    # Nếu an toàn, thêm ô vào danh sách đã chọn
    state["chosen"].add(cell)
    safe_count = len(state["chosen"])
    bomb_count = state["bomb_count"]
    # Tính multiplier động dựa trên số ô an toàn và số bom
    current_multiplier = calculate_multiplier(safe_count, bomb_count)
    state["multiplier"] = current_multiplier
    win_amount = int(state["bet"] * current_multiplier)
    chosen_cells = sorted(list(state["chosen"]))
    chosen_str = ", ".join(str(x) for x in chosen_cells)
    # Dự đoán multiplier nếu chọn thêm 1 ô nữa
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

# Bước 5: Handler cho “Rút tiền đào vàng”
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

# Bước 6: Handler cho “Chơi tiếp”
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
@router.message(F.text == "🃏 Mini Poker")
async def start_poker(message: types.Message):
    user_id = str(message.from_user.id)
    poker_states[user_id] = True
    await message.answer(
        "💰 Nhập số tiền cược, bot sẽ quay ra một tay bài Poker!",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(lambda msg: poker_states.get(str(msg.from_user.id)) == True and msg.text.isdigit())
async def play_poker(message: types.Message):
    user_id = str(message.from_user.id)
    amount = int(message.text)  # Nếu cần dùng số tiền cược cho tính toán
    poker_states[user_id] = False  # Reset trạng thái sau khi cược
    hands = ["Đôi", "Sám", "Sảnh", "Thùng", "Cù Lũ", "Tứ Quý", "Thùng Phá Sảnh"]
    hand = random.choice(hands)
    await message.answer(f"🃏 Tay bài của bạn: {hand}!")
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

# ===================== Xử lý tin nhắn số (cho nạp tiền & đặt cược Tài Xỉu) =====================
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
    if user_id in current_bets:
        if user_balance.get(user_id, 0) < amount:
            await message.answer("⚠️ Bạn không đủ số dư để đặt cược!", reply_markup=main_menu)
            return
        user_balance[user_id] -= amount
        dice_values = []
        for _ in range(3):
            dice_msg = await message.answer_dice(emoji="🎲")
            dice_values.append(dice_msg.dice.value)
            await asyncio.sleep(2)
        total = sum(dice_values)
        result = "Tài" if total >= 11 else "Xỉu"
        bet_choice = current_bets[user_id]["choice"]
        if bet_choice == result:
            winnings = amount * 1.96
            user_balance[user_id] += winnings
            msg_result = f"🎉 Chúc mừng! Bạn đã thắng {winnings:.0f} VNĐ!"
        else:
            msg_result = f"😢 Bạn đã thua cược. Số dư bị trừ: {amount} VNĐ."
        record = {
            "time": datetime.now().isoformat(),
            "game": "Tài Xỉu",
            "choice": bet_choice,
            "bet_amount": amount,
            "result": result,
            "winnings": winnings if bet_choice == result else -amount
        }
        user_history[user_id].append(record)
        del current_bets[user_id]
        save_data(data)
        await message.answer(f"🎲 Kết quả tung xúc xắc: {dice_values[0]}, {dice_values[1]}, {dice_values[2]}\n✨ Tổng điểm: {total} ({result})\n{msg_result}\n💰 Số dư hiện tại của bạn: {user_balance[user_id]} VNĐ", reply_markup=main_menu)
        return
    await message.answer("Vui lòng bấm nút '🎲 Tài Xỉu' và chọn Tài/Xỉu trước khi đặt cược, hoặc chọn lệnh phù hợp.")
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

# ===================== Nút Rút tiền =====================
@router.message(F.text == "💸 Rút tiền")
async def start_withdraw(message: types.Message):
    # Hướng dẫn người dùng nhập thông tin rút tiền theo mẫu:
    withdraw_instruction = (
        "💸 Để rút tiền, vui lòng nhập thông tin theo mẫu sau:\n\n"
        "[Số tiền] [Họ tên] [Ngân hàng] [Số tài khoản]\n\n"
        "📝 Ví dụ: 1000000 NguyenVanA BIDV 1234567890\n\n"
        "📌 Lưu ý:\n"
        "- Số tiền phải nhỏ hơn hoặc bằng số dư hiện tại.\n"
        "- Số tiền rút tối thiểu là 50k.\n"
        "- Họ tên phải khớp với tên chủ tài khoản ngân hàng.\n"
        "- Sau khi kiểm tra, admin sẽ xử lý giao dịch."
    )
    await message.answer(withdraw_instruction, reply_markup=ReplyKeyboardRemove())

# ===================== Xử lý tin nhắn rút tiền =====================
@router.message(lambda msg: msg.from_user.id != ADMIN_ID and msg.text and len(msg.text.split()) >= 4 and msg.text.split()[0].isdigit())
async def process_withdraw_request(message: types.Message):
    user_id = str(message.from_user.id)
    parts = message.text.strip().split()
    amount = int(parts[0])
    
    # Kiểm tra số tiền rút tối thiểu là 50k
    if amount < 50000:
        await message.answer("⚠️ Số tiền rút tối thiểu là 50k. Vui lòng nhập lại thông tin theo mẫu.", reply_markup=main_menu)
        return

    if user_id not in user_balance:
        await message.answer("⚠️ Bạn chưa có tài khoản. Vui lòng /start để tạo tài khoản.", reply_markup=main_menu)
        return
    if user_balance.get(user_id, 0) < amount:
        await message.answer("⚠️ Số dư của bạn không đủ để rút tiền.", reply_markup=main_menu)
        return

    full_name = parts[1]
    bank_name = parts[2]
    account_number = " ".join(parts[3:])  # Cho phép số tài khoản có nhiều từ

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
    admin_message = (
        f"📢 Có yêu cầu rút tiền mới từ user {user_id}:\n"
        f" - Số tiền: {amount} VNĐ\n"
        f" - Họ tên: {full_name}\n"
        f" - Ngân hàng: {bank_name}\n"
        f" - Số tài khoản: {account_number}\n\n"
        "Vui lòng xử lý yêu cầu này."
    )
    await bot.send_message(ADMIN_ID, admin_message)
    await message.answer(
        f"✅ Yêu cầu rút tiền của bạn đã được gửi đến admin.\n"
        f"Chi tiết yêu cầu:\n"
        f" - Số tiền: {amount} VNĐ\n"
        f" - Họ tên: {full_name}\n"
        f" - Ngân hàng: {bank_name}\n"
        f" - Số tài khoản: {account_number}\n\n"
        "Vui lòng chờ admin xử lý.",
        reply_markup=main_menu
    )


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
        BotCommand(command="ruttien", description="Admin duyệt rút tiền"),
        BotCommand(command="admin_sodu", description="Xem số dư tất cả user (Admin)"),
        BotCommand(command="tracuu", description="Xem người chơi (Admin)")
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

