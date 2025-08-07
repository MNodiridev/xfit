# requirements: python-telegram-bot==20.0
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os

TOKEN = os.getenv("TG_BOT_TOKEN")
CLUB_NAME = os.getenv("CLUB_NAME", "X-fit Premium Dushanbe")

def main_menu():
    # Нижняя панель с постоянными кнопками
    return ReplyKeyboardMarkup(
        [
            ["📆 Расписание", "🧑‍🏫 Тренеры"],
            ["💳 Абонементы", "📞 Контакты"]
        ],
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Добро пожаловать в {CLUB_NAME}!\nВыберите нужный раздел:",
        reply_markup=main_menu()
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Команда /menu на всякий случай
    await update.message.reply_text("Меню:", reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Реакция на ЛЮБОЕ текстовое сообщение — всегда возвращаем кнопки
    text = (update.message.text or "").strip()

    if text == "📆 Расписание":
        msg = "📆 Расписание:\nПн–Пт: 7:00–22:00\nСб–Вс: 9:00–20:00"
    elif text == "🧑‍🏫 Тренеры":
        msg = "🧑‍🏫 Тренеры:\n- Али — силовые, функциональные\n- Дилшод — бокс, кроссфит\n- Сабина — стретчинг, пилатес"
    elif text == "💳 Абонементы":
        msg = "💳 Абонементы:\n1 мес — 400 сомони\n3 мес — 1050 сомони\n(пример — подставим ваши цены позже)"
    elif text == "📞 Контакты":
        msg = "📞 Контакты:\n📍 Душанбе, ул. Спортивная, 7\n📱 +992 900 00 00 00"
    else:
        msg = "Выберите пункт меню ниже:"

    await update.message.reply_text(msg, reply_markup=main_menu())

def main():
    if not TOKEN:
        raise RuntimeError("Переменная TG_BOT_TOKEN не задана")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"Бот {CLUB_NAME} запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
