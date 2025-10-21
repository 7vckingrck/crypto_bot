import os
import time
import logging
from datetime import datetime
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

from password_generator import (
    check_rate_limit,
    DEFAULTS,
    generate_multiple_passwords
)

from secure_storage import SecureStorage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

secure_storage = SecureStorage()


async def save_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⚠️ Слишком много запросов. Попробуйте чуть позже.")
        return

    message_parts = update.message.text.split(' ', 2)
    if len(message_parts) < 3:
        await update.message.reply_text(
            "❌ Неправильный формат. Используйте: /save <учетная_запись> <пароль>\n"
            "Пример: /save example@gmail.com mypassword123"
        )
        return

    try:
        _, account, password = message_parts
        
        if secure_storage.account_exists(user.id, account):
            await update.message.reply_text(
                f"⚠️ Учетная запись '{account}' уже существует."
            )
            return

        secure_storage.save_password(user.id, account, password)
        await update.message.reply_text(f"✅ Учетная запись '{account}' успешно сохранена!")
    except Exception as e:
        logger.error(f"Error in save_password: {e}")
        await update.message.reply_text("❌ Произошла ошибка при сохранении учетной записи.")


async def my_passwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⚠️ Слишком много запросов. Попробуйте чуть позже.")
        return

    try:
        passwords = secure_storage.get_passwords(user.id)

        if not passwords:
            await update.message.reply_text("📋 У вас пока нет сохраненных учетных записей.")
            return

        response = "🔐 Ваши сохраненные учетные записи:\n\n"
        for i, acc in enumerate(passwords, 1):
            response += f"{i}. {acc['account']}\n   Пароль: `{acc['password']}`\n   Дата добавления: {acc['date_added']}\n\n"

        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in my_passwords: {e}")
        await update.message.reply_text("❌ Произошла ошибка при загрузке ваших паролей.")


LEVELS = [("Простой 🔰", "simple"), ("Средний ⚙️", "medium"), ("Сложный 🔒", "strong")]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Привет! Я бот для генерации безопасных паролей.\n\n"
        "Я могу:\n"
        "• Генерировать пароли различной сложности\n"
        "• Сохранять ваши учетные записи с паролями\n"
        "• Предоставлять быстрый доступ к сохраненным данным\n\n"
        "Для просмотра всех команд используйте /help"
    )
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"gen:{code}") for label, code in LEVELS],
        [InlineKeyboardButton("🔐 Мои пароли", callback_data="my_passwords")],
        [InlineKeyboardButton("✉️ Группа ТГ", url="https://t.me/bot_creator161")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ Список команд бота:\n\n"
        "🔐 Генерация паролей:\n"
        "/simple [длина] - простой пароль (буквы и цифры)\n"
        "/medium [длина] - средний пароль (буквы разных регистров и цифры)\n"
        "/strong [длина] - сложный пароль (буквы, цифры и символы)\n\n"
        "📚 Управление учетными записями:\n"
        "/save <учетная_запись> <пароль> - сохранить новую учетную запись\n"
        "/mypasswords - посмотреть все сохраненные учетные записи\n\n"
        "🧹 Дополнительно:\n"
        "/clear - очистить чат (удалить последние сообщения)\n"
        "/start - главное меню\n"
        "/help - это сообщение\n\n"
        "Примеры:\n"
        "/simple 10\n"
        "/medium 16\n"
        "/strong 24\n"
        "/save example@gmail.com mypassword123"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            return

    if not (DEFAULTS[level]["min"] <= length <= DEFAULTS[level]["max"]):
        level_names = {"simple": "простой", "medium": "средний", "strong": "сложный"}
        level_name = level_names.get(level, level)
        await update.message.reply_text(
            f"Допустимая длина для {level_name} уровня: от {DEFAULTS[level]['min']} до {DEFAULTS[level]['max']}."
        )
        return

    try:
        passwords = generate_multiple_passwords(level, length, 3)
        
        keyboard = [
            [InlineKeyboardButton("🔄 Сгенерировать еще", callback_data=f"gen:{level}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        pwd_list = "\n".join([f"`{pwd}`" for pwd in passwords])
        msg = f"🔐 Ваши пароли ({level}, длина {length}):\n\n{pwd_list}\n\nВыберите действие:"
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in generate_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при генерации паролей.")


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not check_rate_limit(user.id):
        await query.edit_message_text("⚠️ Слишком много запросов. Попробуйте позже.")
        return

    data = query.data
    if data.startswith("gen:"):
        try:
            level = data.split(":")[1]
            length = DEFAULTS[level]["default"]
            passwords = generate_multiple_passwords(level, length, 3)
            
            keyboard = [
                [InlineKeyboardButton("🔄 Сгенерировать еще", callback_data=f"gen:{level}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            pwd_list = "\n".join([f"`{pwd}`" for pwd in passwords])
            text = f"🔐 Сгенерированы пароли ({level}, длина {length}):\n\n{pwd_list}\n\nМожно указать длину: /{level} <число>"
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in gen handler: {e}")
            await query.edit_message_text("❌ Произошла ошибка при генерации паролей.")
    elif data == "back_to_menu":
        try:
            text = (
                "👋 Привет! Я бот для генерации безопасных паролей.\n\n"
                "Я могу:\n"
                "• Генерировать пароли различной сложности\n"
                "• Сохранять ваши учетные записи с паролями\n"
                "• Предоставлять быстрый доступ к сохраненным данным\n\n"
                "Для просмотра всех команд используйте /help"
            )
            keyboard = [
                [InlineKeyboardButton(label, callback_data=f"gen:{code}") for label, code in LEVELS],
                [InlineKeyboardButton("🔐 Мои пароли", callback_data="my_passwords")],
                [InlineKeyboardButton("✉️ Группа ТГ", url="https://t.me/bot_creator161")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error in back_to_menu handler: {e}")
            await query.edit_message_text("Ошибка при возврате в меню.")
    elif data == "my_passwords":
        try:
            passwords = secure_storage.get_passwords(query.from_user.id)
            
            if not passwords:
                text = "📋 У вас пока нет сохраненных учетных записей."
                keyboard = [
                    [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
                ]
            else:
                text = "🔐 Ваши сохраненные учетные записи:\n\n"
                for i, acc in enumerate(passwords, 1):
                    text += f"{i}. {acc['account']}\n   Пароль: `{acc['password']}`\n   Дата добавления: {acc['date_added']}\n\n"
                
                keyboard = [
                    [InlineKeyboardButton("🗑️ Очистить все", callback_data="clear_passwords")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in my_passwords handler: {e}")
            await query.edit_message_text("❌ Произошла ошибка при загрузке ваших паролей.")
    elif data == "clear_passwords":
        try:
            keyboard = [
                [InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear")],
                [InlineKeyboardButton("❌ Нет, вернуться", callback_data="my_passwords")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("⚠️ Вы уверены, что хотите удалить все сохраненные учетные записи?", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error in clear_passwords handler: {e}")
            await query.edit_message_text("❌ Произошла ошибка при подготовке подтверждения очистки.")
    elif data == "confirm_clear":
        try:
            secure_storage.delete_all_passwords(query.from_user.id)
            text = "🗑️ Все сохраненные учетные записи успешно удалены."
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error in confirm_clear handler: {e}")
            await query.edit_message_text("❌ Произошла ошибка при очистке данных.")
    else:
        try:
            await query.edit_message_text("Неизвестная кнопка.")
        except Exception as e:
            logger.error(f"Error in unknown handler: {e}")


async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⚠️ Слишком много запросов. Попробуйте чуть позже.")
        return
    
    chat_id = update.effective_message.chat_id
    
    try:
        for message_id in range(update.effective_message.message_id - 1, 
                                update.effective_message.message_id - 11, -1):
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                continue
        
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=update.effective_message.message_id)
        except Exception:
            pass
        
        temp_msg = await update.message.reply_text("🗑️ Чат очищен...")
        await context.bot.delete_message(chat_id=chat_id, message_id=temp_msg.message_id)
    except Exception as e:
        await update.message.reply_text("⚠️ Не удалось очистить чат. Некоторые сообщения могут быть защищены от удаления.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Не понял. Используйте /start для вызова меню.")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("simple", generate_command))
    app.add_handler(CommandHandler("medium", generate_command))
    app.add_handler(CommandHandler("strong", generate_command))
    app.add_handler(CommandHandler("save", save_password))
    app.add_handler(CommandHandler("mypasswords", my_passwords))
    app.add_handler(CommandHandler("clear", clear_chat))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()