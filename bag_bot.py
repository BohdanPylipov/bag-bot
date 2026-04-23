import asyncio
import random
import json
import os
from collections import Counter
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==============================
# НАСТРОЙКИ
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_ЗДЕСЬ")
DATA_FILE = "bag_data.json"

# ==============================
# ХРАНЕНИЕ ДАННЫХ
# ==============================

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "history": [],
        "known_users": {},
        "poll_voters": {},
        "poll_out": {},
    }

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_full_name(user: types.User) -> str:
    if user.last_name:
        return f"{user.first_name} {user.last_name}"
    return user.first_name

def build_message_text(data: dict) -> str:
    voters_in = data.get("poll_voters", {})
    voters_out = data.get("poll_out", {})

    text = "*Сегодня тренировка! ⚽️*\n\nГолосуем нажатием ⤵️\n\n"

    if voters_in:
        names_in = "\n".join(f"• {name}" for name in voters_in.values())
        text += f"🙋🏻‍♂️ *Придут ({len(voters_in)}):*\n{names_in}\n\n"
    else:
        text += "🙋🏻‍♂️ *Придут (0):*\n_(Пока пусто 👎🏻)_\n\n"

    if voters_out:
        names_out = "\n".join(f"• {name}" for name in voters_out.values())
        text += f"🙅🏻‍♂️ *Не придут ({len(voters_out)}):*\n{names_out}"
    else:
        text += "🙅🏻‍♂️ *Не придут (0):*\n_(Пока пусто 👍🏻)_"

    return text

# ==============================
# БОТ
# ==============================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_vote_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Буду! 👍🏻", callback_data="im_in"),
            InlineKeyboardButton(text="Не буду! 👎🏻", callback_data="im_out")
        ]
    ])

# ==============================
# КОМАНДЫ
# ==============================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет 👋🏻 Я выбираю дежурного по стирке манишек 🧺\n\n"
        "📋 *Как пользоваться:*\n"
        "1. Тренер пишет /training\n"
        "2. Участники нажимают «Буду! 👍🏻» или «Не буду! 👎🏻»\n"
        "3. Тренер пишет /pick — я выбираю дежурного с учётом истории предыдущих результатов 👌🏻\n\n"
        "⚙️ *Команды:*\n"
        "/training — начать сбор голосов\n"
        "/pick — выбрать дежурного\n"
        "/voters — кто сейчас нажал «Буду»\n"
        "/history — история дежурств ✍🏻\n"
        "/reset — сбросить историю (только админы)",
        parse_mode="Markdown"
    )

@dp.message(Command("training"))
async def cmd_training(message: types.Message):
    data = load_data()
    data["poll_voters"] = {}
    data["poll_out"] = {}
    save_data(data)

    await message.answer(
        build_message_text(data),
        parse_mode="Markdown",
        reply_markup=get_vote_keyboard()
    )

@dp.callback_query(F.data == "im_in")
async def handle_in(callback: types.CallbackQuery):
    data = load_data()
    user = callback.from_user
    user_id = str(user.id)
    full_name = get_full_name(user)

    data["known_users"][user_id] = full_name
    data["poll_voters"][user_id] = full_name
    if "poll_out" not in data:
        data["poll_out"] = {}
    data["poll_out"].pop(user_id, None)
    save_data(data)

    await callback.answer("До встречи! ✍🏻")
    try:
        await callback.message.edit_text(
            build_message_text(data),
            parse_mode="Markdown",
            reply_markup=get_vote_keyboard()
        )
    except Exception:
        pass

@dp.callback_query(F.data == "im_out")
async def handle_out(callback: types.CallbackQuery):
    data = load_data()
    user = callback.from_user
    user_id = str(user.id)
    full_name = get_full_name(user)

    data["known_users"][user_id] = full_name
    if "poll_out" not in data:
        data["poll_out"] = {}
    data["poll_out"][user_id] = full_name
    data.get("poll_voters", {}).pop(user_id, None)
    save_data(data)

    await callback.answer("Не пропадай ☹️")
    try:
        await callback.message.edit_text(
            build_message_text(data),
            parse_mode="Markdown",
            reply_markup=get_vote_keyboard()
        )
    except Exception:
        pass

@dp.message(Command("voters"))
async def cmd_voters(message: types.Message):
    data = load_data()
    voters = data.get("poll_voters", {})

    if not voters:
        await message.answer("📋 Пока никто не нажал «Буду».")
        return

    names = "\n".join(f"• {name}" for name in voters.values())
    await message.answer(
        f"🙋🏻‍♂️ *Придут ({len(voters)} чел.):*\n\n{names}",
        parse_mode="Markdown"
    )

@dp.message(Command("pick"))
async def cmd_pick(message: types.Message):
    data = load_data()
    voters = data.get("poll_voters", {})

    if not voters:
        await message.answer(
            "❌ Никто не нажал «Буду»!\n"
            "Сначала используй /training"
        )
        return

    history = data["history"]
    eligible = {uid: name for uid, name in voters.items() if uid not in history}

    if not eligible:
        await message.answer(
            "Все кто придёт — уже дежурили! 😳\n"
            "Сбрасываю историю и выбираю из всех 🔄"
        )
        data["history"] = []
        save_data(data)
        eligible = voters

    chosen_id, chosen_name = random.choice(list(eligible.items()))

    data["history"].append(chosen_id)
    if len(data["history"]) > 100:
        data["history"] = data["history"][-100:]

    save_data(data)

    skipped = len(voters) - len(eligible)
    skip_note = f"\n_({skipped} из списка — уже дежурили 🤞🏻)_" if skipped > 0 else ""

    await message.answer(
        f"Сегодня сумку берёт: {chosen_name} 😶‍🌫️\n\n"
        f"Выбран из {len(eligible)} 👌🏻{skip_note}"
    )

@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    data = load_data()
    history = data["history"]
    known_users = data.get("known_users", {})

    if not history:
        await message.answer("История пока пуста 📋")
        return

    counts = Counter(history)
    lines = []
    for uid, cnt in counts.most_common():
        name = known_users.get(uid, f"user_{uid}")
        lines.append(f"• {name} — {cnt} раз(а)")

    await message.answer(
        "*История дежурств с сумкой ✍🏻 :*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("Только администраторы могут сбрасывать историю ❌")
            return
    except Exception:
        pass

    data = load_data()
    data["history"] = []
    save_data(data)
    await message.answer("История дежурств сброшена! ✅")

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
