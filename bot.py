# requirements: python-telegram-bot==20.0
import asyncio
import logging
import os
import re
import smtplib
import sqlite3
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime_text import MIMEText

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    Contact,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# === Config via ENV ===
TOKEN = os.getenv("TG_BOT_TOKEN")
CLUB_NAME = os.getenv("CLUB_NAME", "X-fit Premium Dushanbe")
EMAIL_TO = os.getenv("EMAIL_TO", "sales@x-fit.tj")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1") == "1"

DB_PATH = os.getenv("DB_PATH", "guest_visits.sqlite3")

# === Logging ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# === DB init ===
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guest_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            tg_user_id INTEGER,
            tg_username TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def insert_guest(name: str, phone: str, tg_user_id: int, tg_username: str | None) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO guest_visits (name, phone, tg_user_id, tg_username, created_at) VALUES (?,?,?,?,?)",
        (name, phone, tg_user_id, tg_username, datetime.utcnow().isoformat() + "Z"),
    )
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return int(rowid)

def normalize_phone(text: str) -> str | None:
    if not text:
        return None
    # keep + and digits
    digits = re.sub(r"[^\d+]", "", text)
    # Basic sanity: at least 7 digits
    if len(re.sub(r"\D", "", digits)) < 7:
        return None
    # Ensure leading + if it looks like intl without plus
    if digits and digits[0] != "+" and len(re.sub(r"\D", "", digits)) >= 10:
        digits = "+" + re.sub(r"\D", "", digits)
    return digits

def send_email(application_id: int, name: str, phone: str, update: Update):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP not configured; skipping email send.")
        return False

    subject = f"Заявка с ТГ бота №{application_id}"
    body = (
        f"Новая заявка на гостевой визит в {CLUB_NAME}\n\n"
        f"ID заявки: {application_id}\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"TG user: @{(update.effective_user.username or '')}\n"
        f"TG user id: {update.effective_user.id}\n"
        f"Дата (UTC): {datetime.utcnow().isoformat()}Z\n"
    )

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [EMAIL_TO], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False

# === States ===
(
    MAIN_MENU,
    GUEST_NAME,
    GUEST_PHONE_WAIT,
) = range(3)

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📆 Расписание", "🧑‍🏫 Тренеры"],
            ["💬 Жалобы и предложения", "🎟️ Гостевой визит"],
        ],
        resize_keyboard=True,
    )

def guest_phone_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📲 Отправить мой номер из Telegram", request_contact=True)],
            ["↩️ Назад в меню"],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Добро пожаловать в {CLUB_NAME}! Выберите раздел:", reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU

async def to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
    return MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()
    if "гостевой" in text:
        # Start guest visit flow: first ask name
        await update.message.reply_text(
            "🎟️ Гостевой визит.\n\nВведите, пожалуйста, ваше имя (как к вам обращаться)?",
            reply_markup=ReplyKeyboardRemove(),
        )
        return GUEST_NAME
    elif "жалобы" in text:
        await update.message.reply_text(
            "Оставить жалобу/предложение: заполните форму 👉 https://forms.gle/example",
            reply_markup=main_menu_keyboard(),
        )
        return MAIN_MENU
    else:
        await update.message.reply_text("Раздел в разработке. Выберите другой пункт.", reply_markup=main_menu_keyboard())
        return MAIN_MENU

async def guest_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if len(name) < 2:
        await update.message.reply_text("Имя слишком короткое. Введите имя ещё раз:")
        return GUEST_NAME
    context.user_data["guest_name"] = name
    # Ask for phone
    await update.message.reply_text(
        "Отлично! Теперь отправьте номер телефона. "
        "Вы можете:\n• Нажать кнопку ниже, чтобы отправить номер из Telegram\n"
        "• Или просто ввести номер в тексте (например: +992 900 000 000)",
        reply_markup=guest_phone_keyboard(),
    )
    return GUEST_PHONE_WAIT

async def guest_get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = None
    if update.message.contact and isinstance(update.message.contact, Contact):
        phone = normalize_phone(update.message.contact.phone_number)
    else:
        phone = normalize_phone(update.message.text or "")

    if not phone:
        await update.message.reply_text(
            "Не удалось распознать номер. Отправьте контакт кнопкой ниже или введите номер в формате +XXXXXXXXXXX:",
            reply_markup=guest_phone_keyboard(),
        )
        return GUEST_PHONE_WAIT

    name = context.user_data.get("guest_name", "").strip() or "—"
    user = update.effective_user

    # Save to DB
    try:
        application_id = insert_guest(name, phone, user.id, user.username)
    except Exception as e:
        logger.exception("DB insert failed")
        await update.message.reply_text("Произошла ошибка при сохранении заявки. Попробуйте позже.", reply_markup=main_menu_keyboard())
        return MAIN_MENU

    # Send email
    email_ok = send_email(application_id, name, phone, update)

    confirm = (
        f"Спасибо! Заявка №{application_id} принята.\n"
        f"Имя: {name}\nТелефон: {phone}\n\n"
        f"Мы свяжемся с вами для подтверждения гостевого визита."
    )
    if not email_ok:
        confirm += "\n\n⚠️ Письмо на почту не отправлено (настройки почты не заданы)."

    await update.message.reply_text(confirm, reply_markup=main_menu_keyboard())
    context.user_data.pop("guest_name", None)
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard())
    return MAIN_MENU

def build_application() -> Application:
    if not TOKEN:
        raise RuntimeError("TG_BOT_TOKEN is not set")
    app = Application.builder().token(TOKEN).build()

    # Conversation for guest visit
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.Regex("(?i)гостевой"), handle_main_menu)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
            ],
            GUEST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, guest_get_name),
                MessageHandler(filters.Regex("(?i)назад"), to_menu),
            ],
            GUEST_PHONE_WAIT: [
                MessageHandler(filters.CONTACT, guest_get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, guest_get_phone),
                MessageHandler(filters.Regex("(?i)назад"), to_menu),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("menu", to_menu)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    # Quick /menu command
    app.add_handler(CommandHandler("menu", to_menu))
    return app

def main():
    init_db()
    app = build_application()
    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
