#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Password Generator Bot
Author: @bot_creator61
Requirements:
  pip install python-telegram-bot==20.5
Usage:
  export BOT_TOKEN="KEY"
  python bot.py
"""

import os
import time
import logging
import string
import secrets
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Bot token not found. Please set the BOT_TOKEN environment variable.")

RATE_LIMIT_MAX = 15
RATE_LIMIT_WINDOW = 60
_user_requests = {}

DEFAULTS = {
    "simple": {"default": 8, "min": 4, "max": 32},
    "medium": {"default": 12, "min": 6, "max": 64},
    "strong": {"default": 20, "min": 8, "max": 128},
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def check_rate_limit(user_id: int) -> bool:
    """Простая защита от спама."""
    now = time.time()
    ts_list = _user_requests.get(user_id, [])
    ts_list = [t for t in ts_list if now - t < RATE_LIMIT_WINDOW]
    if len(ts_list) >= RATE_LIMIT_MAX:
        _user_requests[user_id] = ts_list
        return False
    ts_list.append(now)
    _user_requests[user_id] = ts_list
    return True


def make_charset(level: str, exclude_ambiguous: bool = True) -> str:
    """Возвращает набор символов для выбранного уровня сложности."""
    AMBIG = {'l', 'I', '1', 'O', '0'}
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    punct = ''.join(ch for ch in string.punctuation if ch not in {'"', "'", '\\', '`'})

    if exclude_ambiguous:
        lower = ''.join(c for c in lower if c not in AMBIG)
        upper = ''.join(c for c in upper if c not in AMBIG)
        digits = ''.join(c for c in digits if c not in AMBIG)

    if level == "simple":
        return lower + digits
    elif level == "medium":
        return lower + upper + digits
    elif level == "strong":
        return lower + upper + digits + punct
    else:
        raise ValueError("Неизвестный уровень сложности")


def generate_password(level: str, length: int) -> str:
    """Генерация безопасного пароля."""
    charset = make_charset(level)
    return ''.join(secrets.choice(charset) for _ in range(length))


def generate_multiple_passwords(level: str, length: int, count: int = 3) -> list:
    """Генерация нескольких паролей."""
    return [generate_password(level, length) for _ in range(count)]

LEVELS = [("Простой 🔰", "simple"), ("Средний ⚙️", "medium"), ("Сложный 🔒", "strong")]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Привет! Я бот для генерации паролей.\n\n"
        "Выбери уровень сложности или используй команды:\n"
        "/simple [длина]\n"
        "/medium [длина]\n"
        "/strong [длина]\n\n"
        "Примеры:\n"
        "• /simple 10\n"
        "• /medium 16\n"
        "• /strong 24\n\n"
        "По умолчанию длина безопасная. Символы вроде кавычек и обратных слешей исключены."
    )
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"gen:{code}") for label, code in LEVELS],
        [InlineKeyboardButton("✉️ Написать автору", url="https://t.me/bot_creator61")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка /simple /medium /strong"""
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⚠️ Слишком много запросов. Попробуйте чуть позже.")
        return

    cmd = update.message.text.split()[0].lstrip('/')
    if cmd not in DEFAULTS:
        await update.message.reply_text("Неизвестная команда.")
        return

    level = cmd
    length = DEFAULTS[level]["default"]

    parts = update.message.text.split()
    if len(parts) > 1:
        try:
            length = int(parts[1])
        except ValueError:
            await update.message.reply_text("Длина должна быть числом.")

    if not (DEFAULTS[level]["min"] <= length <= DEFAULTS[level]["max"]):
        level_names = {"simple": "простой", "medium": "средний", "strong": "сложный"}
        level_name = level_names.get(level, level)
        await update.message.reply_text(
            f"Допустимая длина для {level_name} уровня: от {DEFAULTS[level]['min']} до {DEFAULTS[level]['max']}."
        )
        return

    passwords = generate_multiple_passwords(level, length, 3)

    keyboard = [
        [InlineKeyboardButton("🔄 Сгенерировать еще", callback_data=f"gen:{level}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    pwd_list = "\n".join([f"`{pwd}`" for pwd in passwords])
    msg = f"🔐 Ваши пароли ({level}, длина {length}):\n\n{pwd_list}\n\nВыберите действие:"
    await update.message.reply_text(msg, reply_markup=reply_markup)


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопки под сообщением"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not check_rate_limit(user.id):
        await query.edit_message_text("⚠️ Слишком много запросов. Попробуйте позже.")
        return

    data = query.data
    if data.startswith("gen:"):
        level = data.split(":")[1]
        length = DEFAULTS[level]["default"]
        passwords = generate_multiple_passwords(level, length, 3)

        keyboard = [
            [InlineKeyboardButton("🔄 Сгенерировать еще", callback_data=f"gen:{level}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        pwd_list = "\n".join([f"`{pwd}`" for pwd in passwords])
        text = (
            f"🔐 Сгенерированы пароли ({level}, длина {length}):\n\n{pwd_list}\n\n"
            f"Можно указать длину: /{level} <число>"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    elif data == "back_to_menu":
        text = (
            "👋 Привет! Я бот для генерации паролей.\n\n"
            "Выбери уровень сложности или используй команды:\n"
            "/simple [длина]\n"
            "/medium [длина]\n"
            "/strong [длина]\n\n"
            "Примеры:\n"
            "• /simple 10\n"
            "• /medium 16\n"
            "• /strong 24\n\n"
            "По умолчанию длина безопасная. Символы вроде кавычек и обратных слешей исключены."
        )
        keyboard = [
            [InlineKeyboardButton(label, callback_data=f"gen:{code}") for label, code in LEVELS],
            [InlineKeyboardButton("✉️ Написать автору", url="https://t.me/bot_creator61")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await query.edit_message_text("Неизвестная кнопка.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Не понял. Используйте /start.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("simple", generate_command))
    app.add_handler(CommandHandler("medium", generate_command))
    app.add_handler(CommandHandler("strong", generate_command))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
