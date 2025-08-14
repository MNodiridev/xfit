
# requirements: python-telegram-bot==20.0
import logging
import os
import re
import smtplib
import sqlite3
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

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
# Public info (for "Режим работы и контакты")
WORKING_HOURS = os.getenv("WORKING_HOURS", "Mon–Sun: 06:00–23:00")
CLUB_MAP_URL = os.getenv("CLUB_MAP_URL", "")
CLUB_WEBSITE = os.getenv("CLUB_WEBSITE", "https://x-fit.tj")
CLUB_ADDRESS = os.getenv("CLUB_ADDRESS", "Dushanbe, Muhammadieva St. 24/2")
CLUB_EMAIL = os.getenv("CLUB_EMAIL", "info@x-fit.tj")
CLUB_PHONE = os.getenv("CLUB_PHONE", "+992 48 8888 555")
CLUB_PHONE = _env_multi("CLUB_PHONE", "Вашего звонка ждут", default="+992 48 8888 555")
CLUB_EMAIL = _env_multi("CLUB_EMAIL", "Почтовый ящик", default="info@x-fit.tj")
CLUB_ADDRESS = _env_multi("CLUB_ADDRESS", "Находимся", default="г. Душанбе, ул. Мухаммадиева, 24/2")
CLUB_WEBSITE = _env_multi("CLUB_WEBSITE", "Онлайн", default="https://x-fit.tj")
CLUB_MAP_URL = os.getenv("CLUB_MAP_URL", "")

def _env_multi(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return default


# === Logging ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# === DB init ===
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS guest_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            tg_user_id INTEGER,
            tg_username TEXT,
            created_at TEXT
        )
        '''
    )
    conn.commit()
    conn.close()

def _db_connect():
    return sqlite3.connect(DB_PATH)

def _db_execute(query: str, params: tuple = ()):
    with _db_connect() as conn:
        cur = conn.execute(query, params)
        conn.commit()
        return cur

def insert_guest(name: str, phone: str, tg_user_id: int, tg_username: Optional[str]) -> int:
    cur = _db_execute(
        "INSERT INTO guest_visits (name, phone, tg_user_id, tg_username, created_at) VALUES (?,?,?,?,?)",
        (name, phone, tg_user_id, tg_username, datetime.utcnow().isoformat() + "Z"),
    )
    return int(cur.lastrowid)

def normalize_phone(text: str) -> Optional[str]:
    if not text:
        return None
    digits = re.sub(r"[^\d+]", "", text)
    only_digits = re.sub(r"\D", "", digits)
    if len(only_digits) < 7:
        return None
    if digits and not digits.startswith("+") and len(only_digits) >= 10:
        digits = "+" + only_digits
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
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [EMAIL_TO], msg.as_string())
        else:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [EMAIL_TO], msg.as_string())
        return True
    except Exception:
        logger.exception("Email send failed")
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


# === Public info text ===
def contacts_text():
    lines = [
        "📍 Режим работы:",
        WORKING_HOURS,
        "",
        "📞 Контакты:",
        CLUB_PHONE,
        CLUB_EMAIL,
        "",
        "📍 Адрес:",
        CLUB_ADDRESS,
    ]
    if CLUB_WEBSITE:
        lines.extend(["", "🌐 Сайт:", CLUB_WEBSITE])
    if CLUB_MAP_URL:
        lines.extend(["", "🗺️ Карта:", CLUB_MAP_URL])
    return "\n".join(lines)

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

async def _reply_menu(update: Update, text: str):
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

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
    await _reply_menu(update, f"Добро пожаловать в {CLUB_NAME}! Выберите раздел:")
    return MAIN_MENU

async def to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply_menu(update, "Главное меню:")
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
        await _reply_menu(update, "Оставить жалобу/предложение: заполните форму 👉 https://forms.gle/example")
        return MAIN_MENU
    elif "режим работы" in text or "контакты" in text:
        await _reply_menu(update, contacts_text())
        return MAIN_MENU

    else:
        await _reply_menu(update, "Раздел в разработке. Выберите другой пункт.")
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
        await _reply_menu(update, "Произошла ошибка при сохранении заявки. Попробуйте позже.")
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

    await _reply_menu(update, confirm)
    context.user_data.pop("guest_name", None)
    return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await _reply_menu(update, "Отменено.")
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
