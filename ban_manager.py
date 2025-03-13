@router.message(Command("ban"))
async def handle_ban(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Bạn không có quyền sử dụng lệnh này.")
        return
    
    args = message.text.split()[1:]
    if len(args) < 2:
        await message.reply("Usage: /ban [user_id] [reason]")
        return
    
    user_id = args[0]
    reason = " ".join(args[1:])
    
    ban_user(user_id, reason)
    await message.reply(f"Đã cấm user {user_id} vì: {reason}")

@router.message(Command("unban"))
async def handle_unban(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Bạn không có quyền sử dụng lệnh này.")
        return
    
    args = message.text.split()[1:]
    if len(args) < 1:
        await message.reply("Usage: /unban [user_id]")
        return
    
    user_id = args[0]
    
    if unban_user(user_id):
        await message.reply(f"Đã gỡ cấm user {user_id}.")
    else:
        await message.reply("Người dùng này không bị cấm.")

@router.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    
    if is_banned(user_id):
        reason = get_ban_reason(user_id)
        await message.reply(f"Bạn đã bị admin cấm tài khoản.\nLý do: {reason}\nLiên hệ admin nếu có thắc mắc.", reply_markup=ReplyKeyboardRemove())
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Nút 1"), KeyboardButton(text="Nút 2")],
                [KeyboardButton(text="Nút 3")]
            ],
            resize_keyboard=True
        )
        await message.reply("Chào mừng bạn đến với bot!", reply_markup=keyboard)
