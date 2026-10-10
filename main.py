import random
import sqlite3
from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==================== НАЛАШТУВАННЯ ====================

TOKEN = "8957705769:AAEaVP6_Mrm0s56foRqIf6yJ0-wsMZJdb9k"
DB = "gamemaster.db"

# ==================== БАЗА ДАНИХ ====================

def connect():
    return sqlite3.connect(DB)


def init_db():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
                name TEXT,
                username TEXT,
                coins INTEGER DEFAULT 100,
                xp INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                games INTEGER DEFAULT 0,
                quiz_correct INTEGER DEFAULT 0,
                best_guess INTEGER DEFAULT 0,
                daily_date TEXT DEFAULT '',
                streak INTEGER DEFAULT 0
            )
        """)


def player(user):
    with connect() as db:
        db.execute("""
            INSERT OR IGNORE INTO players (id, name, username)
            VALUES (?, ?, ?)
        """, (user.id, user.first_name or "Гравець", user.username or ""))

        db.execute("""
            UPDATE players SET name=?, username=? WHERE id=?
        """, (user.first_name or "Гравець", user.username or "", user.id))

        db.row_factory = sqlite3.Row
        return db.execute(
            "SELECT * FROM players WHERE id=?", (user.id,)
        ).fetchone()


def update_player(uid, coins=0, xp=0, wins=0, losses=0,
                  games=0, quiz_correct=0, best_guess=None):
    with connect() as db:
        db.execute("""
            UPDATE players
            SET coins=MAX(0, coins+?),
                xp=xp+?,
                wins=wins+?,
                losses=losses+?,
                games=games+?,
                quiz_correct=quiz_correct+?
            WHERE id=?
        """, (coins, xp, wins, losses, games, quiz_correct, uid))

        if best_guess is not None:
            db.execute("""
                UPDATE players SET best_guess=?
                WHERE id=? AND (best_guess=0 OR best_guess>?)
            """, (best_guess, uid, best_guess))


# ==================== МЕНЮ ====================

def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Вгадай число", callback_data="guess"),
            InlineKeyboardButton("✊ КНП", callback_data="rps"),
        ],
        [
            InlineKeyboardButton("🧠 Вікторина", callback_data="quiz"),
            InlineKeyboardButton("👤 Профіль", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("🪙 Монетки", callback_data="coins"),
            InlineKeyboardButton("🏆 Рейтинг", callback_data="top"),
        ],
        [
            InlineKeyboardButton("🎁 Щоденний бонус", callback_data="daily"),
            InlineKeyboardButton("📜 Досягнення", callback_data="achievements"),
        ],
        [InlineKeyboardButton("❔ Допомога", callback_data="help")]
    ])


def back():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Головне меню", callback_data="menu")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player(update.effective_user)
    context.user_data.pop("guess", None)

    await update.effective_message.reply_text(
        "🎮 GAME MASTER\n\n"
        "Вітаю в ігровому клубі!\n\n"
        "🎲 Грай у мініігри.\n"
        "🪙 Заробляй монети.\n"
        "⭐ Отримуй досвід і рівні.\n"
        "🏆 Змагайся з іншими гравцями.\n"
        "🎁 Забирай щоденні бонуси.\n\n"
        "Обирай, що будемо робити!",
        reply_markup=menu()
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "❔ ДОПОМОГА\n\n"
        "/start — головне меню\n"
        "/guess — вгадай число\n"
        "/rps — камінь, ножиці, папір\n"
        "/quiz — вікторина\n"
        "/profile — профіль\n"
        "/top — рейтинг\n"
        "/daily — щоденний бонус\n"
        "/coins — баланс монет\n\n"
        "Монети віртуальні й не мають грошової вартості.",
        reply_markup=menu()
    )


# ==================== ГРА: ВГАДАЙ ЧИСЛО ====================

async def guess_start(query, context):
    context.user_data.pop("guess", None)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Легко: 1–20", callback_data="g_easy")],
        [InlineKeyboardButton("🟡 Середньо: 1–50", callback_data="g_medium")],
        [InlineKeyboardButton("🔴 Важко: 1–100", callback_data="g_hard")],
        [InlineKeyboardButton("🏠 Меню", callback_data="menu")]
    ])

    await query.edit_message_text(
        "🎲 ВГАДАЙ ЧИСЛО!\n\n"
        "Я загадаю число, а ти спробуєш його відгадати.\n"
        "Чим швидше вгадаєш, тим більше монет отримаєш!\n\n"
        "Обирай складність:",
        reply_markup=keyboard
    )


async def guess_begin(query, context, difficulty):
    settings = {
        "easy": (20, 5, 15),
        "medium": (50, 7, 30),
        "hard": (100, 10, 60)
    }

    maximum, attempts, reward = settings[difficulty]

    context.user_data["guess"] = {
        "number": random.randint(1, maximum),
        "maximum": maximum,
        "attempts": attempts,
        "used": 0,
        "reward": reward
    }

    await query.edit_message_text(
        f"🎲 Я загадав число від 1 до {maximum}!\n\n"
        f"У тебе є {attempts} спроб.\n"
        "Напиши число повідомленням у чат.\n\n"
        "Якщо хочеш зупинитися, натисни кнопку.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏳️ Здатися", callback_data="giveup")],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu")]
        ])
    )


async def guess_message(update, context):
    game = context.user_data.get("guess")

    if not game:
        return False

    text = update.effective_message.text.strip()

    if not text.isdigit():
        await update.effective_message.reply_text(
            "🔢 Введи ціле додатне число!"
        )
        return True

    number = int(text)

    if not 1 <= number <= game["maximum"]:
        await update.effective_message.reply_text(
            f"Число має бути від 1 до {game['maximum']}."
        )
        return True

    game["used"] += 1
    target = game["number"]

    if number == target:
        bonus = max(0, (game["attempts"] - game["used"]) * 3)
        reward = game["reward"] + bonus

        update_player(
            update.effective_user.id,
            coins=reward,
            xp=25,
            wins=1,
            games=1,
            best_guess=game["used"]
        )

        context.user_data.pop("guess", None)

        await update.effective_message.reply_text(
            f"🎉 ТИ ВГАДАВ!\n\n"
            f"Загадане число: {target}\n"
            f"Спроб використано: {game['used']}\n\n"
            f"🪙 Нагорода: +{reward} монет\n"
            f"⭐ Досвід: +25 XP\n"
            f"⚡ Бонус за швидкість: +{bonus}",
            reply_markup=menu()
        )
        return True

    remaining = game["attempts"] - game["used"]

    if remaining <= 0:
        update_player(
            update.effective_user.id, losses=1, games=1
        )
        context.user_data.pop("guess", None)

        await update.effective_message.reply_text(
            f"💥 Спроби закінчилися!\n"
            f"Правильне число було: {target}.",
            reply_markup=menu()
        )
        return True

    hint = "⬆️ Загадане число БІЛЬШЕ!" if number < target else \
           "⬇️ Загадане число МЕНШЕ!"

    await update.effective_message.reply_text(
        f"{hint}\nСпроб залишилося: {remaining}"
    )
    return True


# ==================== ГРА: КАМІНЬ, НОЖИЦІ, ПАПІР ====================

async def rps_start(query):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🪨 Камінь", callback_data="r_rock"),
            InlineKeyboardButton("📄 Папір", callback_data="r_paper"),
            InlineKeyboardButton("✂️ Ножиці", callback_data="r_scissors")
        ],
        [InlineKeyboardButton("🏠 Меню", callback_data="menu")]
    ])

    await query.edit_message_text(
        "✊ КАМІНЬ, НОЖИЦІ, ПАПІР!\n\n"
        "Обирай свій хід і змагайся з ботом.",
        reply_markup=keyboard
    )


async def rps_play(query, choice):
    options = {
        "rock": "🪨 Камінь",
        "paper": "📄 Папір",
        "scissors": "✂️ Ножиці"
    }

    beats = {
        "rock": "scissors",
        "scissors": "paper",
        "paper": "rock"
    }

    computer = random.choice(list(options))
    uid = query.from_user.id

    if choice == computer:
        result = "🤝 Нічия! +3 монети"
        update_player(uid, coins=3, xp=5, games=1)

    elif beats[choice] == computer:
        result = "🏆 ТИ ПЕРЕМІГ! +15 монет і +15 XP"
        update_player(uid, coins=15, xp=15, wins=1, games=1)

    else:
        result = "🤖 Цього разу переміг бот!"
        update_player(uid, losses=1, games=1)

    await query.edit_message_text(
        f"✊ КАМІНЬ, НОЖИЦІ, ПАПІР\n\n"
        f"Твій вибір: {options[choice]}\n"
        f"Вибір бота: {options[computer]}\n\n"
        f"{result}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Ще раз", callback_data="rps")],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu")]
        ])
    )


# ==================== ГРА: ВІКТОРИНА ====================

QUESTIONS = [
    ("Яка столиця України?", ["Львів", "Київ", "Одеса", "Харків"], 1),
    ("Скільки буде 7 × 8?", ["54", "56", "64", "48"], 1),
    ("Яка планета найближча до Сонця?",
     ["Земля", "Марс", "Меркурій", "Венера"], 2),
    ("Скільки днів у високосному році?",
     ["364", "365", "366", "367"], 2),
    ("Яка найбільша тварина на Землі?",
     ["Слон", "Синій кит", "Жирафа", "Акула"], 1),
    ("Якою мовою пишуть програми у файлах .py?",
     ["Python", "HTML", "CSS", "Java"], 0),
    ("Скільки хвилин у трьох годинах?",
     ["120", "150", "180", "200"], 2),
    ("Який океан найбільший?",
     ["Атлантичний", "Тихий", "Індійський", "Північний Льодовитий"], 1),
    ("Який колір утворюється з синього та жовтого?",
     ["Зелений", "Червоний", "Фіолетовий", "Чорний"], 0),
    ("Скільки сторін має трикутник?",
     ["2", "3", "4", "5"], 1),
    ("Яка столиця Франції?",
     ["Рим", "Париж", "Берлін", "Мадрид"], 1),
    ("Який газ потрібен людям для дихання?",
     ["Кисень", "Гелій", "Водень", "Метан"], 0),
]


async def quiz_start(query, context):
    question = random.choice(QUESTIONS)
    context.user_data["quiz"] = question

    buttons = []
    for i, answer in enumerate(question[1]):
        buttons.append([
            InlineKeyboardButton(
                f"{'ABCD'[i]}. {answer}",
                callback_data=f"q_{i}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🏠 Меню", callback_data="menu")
    ])

    await query.edit_message_text(
        f"🧠 ВІКТОРИНА\n\n{question[0]}\n\n"
        "За правильну відповідь: +10 монет і +10 XP.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def quiz_answer(query, context, answer):
    question = context.user_data.pop("quiz", None)

    if not question:
        await query.answer("Запусти нову вікторину!", show_alert=True)
        return

    if answer == question[2]:
        update_player(
            query.from_user.id,
            coins=10,
            xp=10,
            wins=1,
            games=1,
            quiz_correct=1
        )
        result = "✅ ПРАВИЛЬНО!\n+10 монет і +10 XP!"
    else:
        update_player(query.from_user.id, losses=1, games=1)
        correct = question[1][question[2]]
        result = f"❌ Неправильно!\nПравильна відповідь: {correct}"

    await query.edit_message_text(
        f"🧠 ВІКТОРИНА\n\n{result}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❓ Наступне питання", callback_data="quiz")],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu")]
        ])
    )


# ==================== ПРОФІЛЬ ====================

async def profile_show(query):
    p = player(query.from_user)
    level = p["xp"] // 100 + 1
    progress = p["xp"] % 100
    bar = "🟩" * (progress // 10) + "⬜" * (10 - progress // 10)

    total = p["wins"] + p["losses"]
    rate = round(p["wins"] / total * 100) if total else 0

    await query.edit_message_text(
        f"👤 ПРОФІЛЬ ГРАВЦЯ\n\n"
        f"Ім'я: {p['name']}\n"
        f"🪙 Монети: {p['coins']}\n"
        f"⭐ Рівень: {level}\n"
        f"✨ Досвід: {p['xp']} XP\n"
        f"{bar} {progress}/100 до наступного рівня\n\n"
        f"🎮 Зіграно ігор: {p['games']}\n"
        f"🏆 Перемог: {p['wins']}\n"
        f"💥 Поразок: {p['losses']}\n"
        f"📊 Відсоток перемог: {rate}%\n"
        f"🧠 Правильних відповідей: {p['quiz_correct']}\n"
        f"🎲 Рекорд вгадування: "
        f"{p['best_guess'] if p['best_guess'] else 'ще немає'}",
        reply_markup=back()
    )


# ==================== МОНЕТКИ ====================

async def coins_show(query):
    p = player(query.from_user)

    await query.edit_message_text(
        f"🪙 ТВІЙ ГАМАНЕЦЬ\n\n"
        f"Баланс: {p['coins']} монет\n\n"
        "Як заробити:\n"
        "🎲 Вгадай число — до 60 монет\n"
        "✊ Перемога в КНП — 15 монет\n"
        "🧠 Правильна відповідь — 10 монет\n"
        "🎁 Щоденний бонус — від 50 монет\n\n"
        "Монети віртуальні й не мають реальної вартості.",
        reply_markup=back()
    )


# ==================== РЕЙТИНГ ====================

async def top_show(query, order="coins"):
    allowed = {
        "coins": "coins",
        "wins": "wins",
        "xp": "xp"
    }
    order = allowed.get(order, "coins")

    with connect() as db:
