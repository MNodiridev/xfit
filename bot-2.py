
# requirements: python-telegram-bot==20.0
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import os
import re
import sqlite3
from datetime import datetime
import smtplib
from email.message import EmailMessage

TOKEN = os.getenv("TG_BOT_TOKEN")
CLUB_NAME = os.getenv("CLUB_NAME", "X-fit Premium Dushanbe")

# --- Email / SMTP settings ---
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM") or SMTP_USER
EMAIL_TO = "sales@x-fit.tj"

# --- DB settings ---
DB_PATH = os.getenv("DB_PATH", "guest_visits.db")

# --- States for conversation ---
ASK_NAME, ASK_PHONE = range(2)

# --- Simple phone regex (accepts +country and digits, spaces, dashes, parentheses) ---
PHONE_RE = re.compile(r"^[+]?[-() 0-9]{6,20}$")

# Feedback form (existing)
FEEDBACK_FORM_URL = os.getenv(
    "FEEDBACK_FORM_URL",
    "https://docs.google.com/forms/d/e/1FAIpQLSdg9cKHTec26MQhBa13T5nefHNKaUnaXxEOiCaAnzPoeZwO4g/viewform?usp=header/viewform",
)

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["📆 Расписание", "🧑‍🏫 Тренеры"],
            ["💳 Абонементы", "📞 Контакты"],
            ["🎟️ Гостевой визит", "✍ Жалобы и предложения"],
        ],
        resize_keyboard=True,
    )

# --------------- DB ---------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS guest_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        '''
    )
    conn.commit()
    conn.close()

def insert_request(tg_user_id: int, name: str, phone: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO guest_requests (tg_user_id, name, phone, created_at) VALUES (?, ?, ?, ?)",
        (tg_user_id, name, phone, datetime.utcnow().isoformat() + "Z"),
    )
    conn.commit()
    req_id = cur.lastrowid  # sequential unique number
    conn.close()
    return req_id

# --------------- EMAIL ---------------
def send_email(subject: str, body: str) -> None:
    if not (SMTP_HOST and SMTP_PORT and EMAIL_FROM and EMAIL_TO):
        print("[EMAIL] SMTP env is not fully configured. Subject:", subject)
        print("[EMAIL] Body:\n", body)
        return

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

# --------------- HANDLERS ---------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Добро пожаловать в {CLUB_NAME}! Выберите раздел:", reply_markup=main_menu()
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню:", reply_markup=main_menu())

async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"✍ Оставьте жалобу/предложение по ссылке:\n{FEEDBACK_FORM_URL}",
        reply_markup=main_menu(),
    )

# ---- Guest visit flow ----
def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True, one_time_keyboard=True)

async def guest_visit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎟️ Гостевой визит. Пожалуйста, отправьте *Имя и Фамилию* одним сообщением.",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )
    return ASK_NAME

async def guest_visit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not name or name.lower() == "отмена":
        await update.message.reply_text("Отменено.", reply_markup=main_menu())
        return ConversationHandler.END
    if len(name) < 2:
        await update.message.reply_text("Имя слишком короткое. Укажите корректное имя.")
        return ASK_NAME
    context.user_data["guest_name"] = name
    await update.message.reply_text(
        "Спасибо! Теперь введите *контактный номер телефона* (например, +992 900 00 00 00).",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )
    return ASK_PHONE

async def guest_visit_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text.lower() == "отмена":
        await update.message.reply_text("Отменено.", reply_markup=main_menu())
        return ConversationHandler.END

    if not PHONE_RE.match(text):
        await update.message.reply_text(
            "Похоже на некорректный номер. Допустимы цифры, пробелы, скобки, дефисы и +. Попробуйте ещё раз."
        )
        return ASK_PHONE

    name = context.user_data.get("guest_name", "").strip()
    phone = text
    tg_user_id = update.effective_user.id if update.effective_user else None

    # Save to DB -> get sequential ID
    req_id = insert_request(tg_user_id, name, phone)

    # Email
    subject = f"Заявка из бота №{req_id}"
    body = (
        f"Новая заявка на гостевой визит\n"
        f"№: {req_id}\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"TG user id: {tg_user_id}\n"
        f"Клуб: {CLUB_NAME}\n"
        f"Время: {datetime.utcnow().isoformat()}Z"
    )
    try:
        send_email(subject, body)
        email_status = "Заявка отправлена на почту и сохранена."
    except Exception as e:
        email_status = f"Заявка сохранена, но отправка на почту не удалась: {e}"

    await update.message.reply_text(
        f"Спасибо! {email_status}\nВаш номер заявки: №{req_id}. С вами свяжутся в ближайшее время.",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "📆 Расписание":
        msg = "📆 Расписание:\nПн–Пт: 6:00–23:00\nСб–Вс: 7:00–22:00"
    elif text == "🧑‍🏫 Тренеры":
        msg = "🧑‍🏫 Тренеры:\n- Али — силовые, функциональные\n- Дилшод — бокс, кроссфит\n- Сабина — стретчинг, пилатес"
    elif text == "💳 Абонементы":
        msg = "💳 Абонементы:\n1 мес — 400 сомони\n3 мес — 1050 сомони\n(пример — подставим ваши цены позже)"
    elif text == "📞 Контакты":
        msg = "📞 Контакты:\n📍 Душанбе, ул. Мухаммадиева, 24/2\n📱 +992 48 8888 555"
    elif text == "✍ Жалобы и предложения":
        msg = f"✍ Оставьте жалобу/предложение по ссылке:\n{FEEDBACK_FORM_URL}"
    elif text == "🎟️ Гостевой визит":
        return await guest_visit_entry(update, context)
    else:
        msg = "Выберите пункт меню ниже:"

    await update.message.reply_text(msg, reply_markup=main_menu())

def build_app() -> Application:
    if not TOKEN:
        raise RuntimeError("Переменная TG_BOT_TOKEN не задана")

    init_db()

    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("feedback", feedback))

    # Guest visit conversation
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎟️ Гостевой визит$"), guest_visit_entry)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, guest_visit_name)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, guest_visit_phone)],
        },
        fallbacks=[MessageHandler(filters.Regex("^Отмена$"), guest_visit_entry)],
        allow_reentry=True,
    )
    app.add_handler(conv)

    # Fallback text handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app

def main():
    app = build_app()
    print(f"Бот {CLUB_NAME} запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
