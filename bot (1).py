import json
import logging
import os
import random
from dataclasses import dataclass, field

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН")
QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "questions.json")


@dataclass
class UserSession:
    order: list = field(default_factory=list)
    current: int = 0
    score: int = 0


sessions: dict[int, UserSession] = {}


def load_questions() -> list[dict]:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


QUESTIONS = load_questions()


def build_question_keyboard(q_index: int, options: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=opt, callback_data=f"answer:{q_index}:{i}")]
        for i, opt in enumerate(options)
    ]
    return InlineKeyboardMarkup(buttons)


async def send_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = sessions[chat_id]

    if session.current >= len(session.order):
        await context.bot.send_message(
            chat_id,
            f"🏁 Викторина окончена!\nТвой результат: {session.score} из {len(session.order)}.\n\n"
            "Хочешь сыграть ещё раз? Введи /quiz",
        )
        del sessions[chat_id]
        return

    q_pos = session.order[session.current]
    question = QUESTIONS[q_pos]
    text = f"❓ Вопрос {session.current + 1}/{len(session.order)}:\n\n{question['question']}"
    keyboard = build_question_keyboard(q_pos, question["options"])
    await context.bot.send_message(chat_id, text, reply_markup=keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Привет! Я бот-викторина.\n\n"
        "Команды:\n"
        "/quiz — начать новую игру\n"
        "/score — узнать текущий счёт\n"
        "/stop — остановить игру"
    )


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    order = list(range(len(QUESTIONS)))
    random.shuffle(order)
    sessions[chat_id] = UserSession(order=order, current=0, score=0)
    await update.message.reply_text("🎮 Начинаем викторину! Отвечай на вопросы, нажимая кнопки.")
    await send_question(chat_id, context)


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = sessions.get(chat_id)
    if not session:
        await update.message.reply_text("Сейчас нет активной игры. Введи /quiz, чтобы начать.")
        return
    await update.message.reply_text(
        f"📊 Текущий счёт: {session.score} из {session.current} отвеченных вопросов."
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id in sessions:
        del sessions[chat_id]
        await update.message.reply_text("Игра остановлена. Введи /quiz, чтобы начать заново.")
    else:
        await update.message.reply_text("Сейчас нет активной игры.")


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    session = sessions.get(chat_id)
    if not session:
        await query.edit_message_text("Эта игра уже завершена. Введи /quiz, чтобы начать новую.")
        return

    _, q_index_str, choice_str = query.data.split(":")
    q_index = int(q_index_str)
    choice = int(choice_str)

    expected_q_index = session.order[session.current]
    if q_index != expected_q_index:
        # Пользователь нажал на кнопку от старого вопроса
        return

    question = QUESTIONS[q_index]
    correct_index = question["correct"]
    is_correct = choice == correct_index

    if is_correct:
        session.score += 1
        result_text = "✅ Верно!"
    else:
        correct_text = question["options"][correct_index]
        result_text = f"❌ Неверно. Правильный ответ: {correct_text}"

    await query.edit_message_text(
        f"{question['question']}\n\n{result_text}"
    )

    session.current += 1
    await send_question(chat_id, context)


def main() -> None:
    if BOT_TOKEN == "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН":
        raise RuntimeError(
            "Не задан токен бота. Установи переменную окружения BOT_TOKEN "
            "или впиши токен напрямую в bot.py"
        )

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("score", score))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CallbackQueryHandler(handle_answer, pattern=r"^answer:"))

    logger.info("Бот запущен, ожидаю сообщения...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
