import asyncio
import random
import json
import os
from collections import Counter
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# ==============================
# НАСТРОЙКИ
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_ЗДЕСЬ")
DATA_FILE = "bag_data.json"

# Варианты ответа в опросе, которые считаются "Буду"
YES_KEYWORDS = ["буду"]

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
        "last_poll_id": None,
        "poll_yes_option": None,
        "poll_voters": {},
    }

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==============================
# БОТ
# ==============================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def is_yes_option(text: str) -> bool:
    return text.strip().lower() == "буду"


@dp.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer):
    data = load_data()

    if poll_answer.poll_id != data.get("last_poll_id"):
        return

    user = poll_answer.user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else user.full_name

    data["known_users"][user_id] = username

    yes_option = data.get("poll_yes_option")

    if yes_option is not None and yes_option in poll_answer.option_ids:
        data["poll_voters"][user_id] = username
    else:
        data["poll_voters"].pop(user_id, None)

    save_data(data)


@dp.message(F.poll)
async def handle_poll_message(message: types.Message):
    poll = message.poll
    data = load_data()

    yes_index = None
    for i, option in enumerate(poll.options):
        if is_yes_option(option.text):
            yes_index = i
            break

    if yes_index is None:
        return

    data["last_poll_id"] = poll.id
    data["poll_yes_option"] = yes_index
    data["poll_voters"] = {}
    save_data(data)

    option_text = poll.options[yes_index].text
    await message.reply(
        f"✅ Отслеживаю опрос!\n"
        f"Считаю голоса за вариант: *\"{option_text}\"*\n\n"
        f"Когда все проголосуют — используйте /pick",
        parse_mode="Markdown"
    )


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! 👋🏻 Я выбираю кто забирает стирать манишки 😶‍🌫\n\n"
        "📋 *Как пользоваться:*\n"
        "1. Тренер создаёт опрос с вариантом *«Буду»*\n"
        "2. Участники голосуют\n"
        "3. Тренер пишет /pick — я выбираю случайного\n\n"
        "⚙️ *Команды:*\n"
        "/pick — выбрать кто несёт сумку\n"
        "/voters — кто сейчас проголосовал «Буду»\n"
        "/history — история дежурств\n"
        "/reset — сбросить историю (только админы)",
        parse_mode="Markdown"
    )


@dp.message(Command("voters"))
async def cmd_voters(message: types.Message):
    data = load_data()
    voters = data.get("poll_voters", {})

    if not voters:
        await message.answer("📋 Пока никто не проголосовал «Буду» в последнем опросе.")
        return

    names = "\n".join(f"• {name}" for name in voters.values())
    await message.answer(
        f"✋ *Проголосовали «Буду»* ({len(voters)} чел.):\n\n{names}",
        parse_mode="Markdown"
    )


@dp.message(Command("pick"))
async def cmd_pick(message: types.Message):
    data = load_data()
    voters = data.get("poll_voters", {})

    if not voters:
        await message.answer(
            "❌ Никто не проголосовал «Буду» в последнем опросе.\n"
            "Убедитесь что опрос создан и бот его видит."
        )
        return

    history = data["history"]
    eligible = {uid: name for uid, name in voters.items() if uid not in history}

    if not eligible:
        await message.answer(
            "🔄 Все кто пришёл — уже стирали!\n"
            "Сбрасываю историю и выбираю из всех."
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
    skip_note = f"\n_(пропущено {skipped} чел. — уже стирали!)_" if skipped > 0 else ""

    await message.answer(
    f"Сегодня манишки забирает: {chosen_name} 😶‍🌫️\n\n"
    f"Выбран из {len(eligible)} тренировавшихся тигров 🐯"
)


@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    data = load_data()
    history = data["history"]
    known_users = data.get("known_users", {})

    if not history:
        await message.answer("📋 История пока пуста.")
        return

    counts = Counter(history)
    lines = []
    for uid, cnt in counts.most_common():
        name = known_users.get(uid, f"user_{uid}")
        lines.append(f"• {name} — {cnt} раз(а)")

    await message.answer(
        "📋 *История дежурств стирки:*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("❌ Только администраторы могут сбрасывать историю.")
            return
    except Exception:
        pass

    data = load_data()
    data["history"] = []
    save_data(data)
    await message.answer("✅ История дежурств стирки сброшена!")


async def main():
    print("Бот запущен!")
    await dp.start_polling(bot, allowed_updates=["message", "poll_answer", "poll"])

if __name__ == "__main__":
    asyncio.run(main())
