# requirements: python-telegram-bot==20.0
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os

TOKEN = os.getenv("TG_BOT_TOKEN")
CLUB_NAME = os.getenv("CLUB_NAME", "X-fit Premium Dushanbe")

# Публичная ссылка на Google Form (возьмём из Google Apps Script после createForm)
FEEDBACK_FORM_URL = os.getenv("FEEDBACK_FORM_URL", "https://docs.google.com/forms/d/ВАША_ССЫЛКА/viewform")

def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["📆 Расписание", "🧑‍🏫 Тренеры"],
            ["💳 Абонементы", "📞 Контакты"],
            ["✍ Жалобы и предложения"]
        ],
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Добро пожаловать в {CLUB_NAME}!\nВыберите нужный раздел:",
        reply_markup=main_menu()
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню:", reply_markup=main_menu())

async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"✍ Оставьте жалобу, предложение или благодарность по ссылке:\n{FEEDBACK_FORM_URL}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "📆 Расписание":
        msg = "📆 Расписание:\nПн–Пт: 7:00–22:00\nСб–Вс: 9:00–20:00"
    elif text == "🧑‍🏫 Тренеры":
        msg = "🧑‍🏫 Тренеры:\n- Али — силовые, функциональные\n- Дилшод — бокс, кроссфит\n- Сабина — стретчинг, пилатес"
    elif text == "💳 Абонементы":
        msg = "💳 Абонементы:\n1 мес — 400 сомони\n3 мес — 1050 сомони\n(пример — подставим ваши цены позже)"
    elif text == "📞 Контакты":
        msg = "📞 Контакты:\n📍 Душанбе, ул. Спортивная, 7\n📱 +992 900 00 00 00"
    elif text == "✍ Жалобы и предложения":
        msg = f"✍ Оставьте жалобу, предложение или благодарность по ссылке:\n{FEEDBACK_FORM_URL}"
    else:
        msg = "Выберите пункт меню ниже:"

    await update.message.reply_text(msg, reply_markup=main_menu())

def main():
    if not TOKEN:
        raise RuntimeError("Переменная TG_BOT_TOKEN не задана")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("feedback", feedback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"Бот {CLUB_NAME} запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
