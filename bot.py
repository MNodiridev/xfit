
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import os

TOKEN = os.getenv("TG_BOT_TOKEN")

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📆 Расписание", callback_data="schedule")],
        [InlineKeyboardButton("🧑‍🏫 Тренеры", callback_data="trainers")],
        [InlineKeyboardButton("💳 Абонементы", callback_data="pricing")],
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать в X-fit Premium Dushanbe!\nВыберите нужный раздел:",
        reply_markup=get_main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "schedule":
        await query.edit_message_text("📆 Расписание:\nПн–Пт: 7:00–23:00\nСб–Вс: 9:00–20:00")
    elif query.data == "trainers":
        await query.edit_message_text("🧑‍🏫 Наши тренеры:\n- Али\n- Дилшод\n- Сабина")
    elif query.data == "pricing":
        await query.edit_message_text("💳 Абонементы:\n1 мес – 400 сомони\n3 мес – 1050 сомони")
    elif query.data == "contacts":
        await query.edit_message_text("📞 Контакты:\n📍 г. Душанбе, ул. Спортивная, 7\n📱 +992 900 00 00 00")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
