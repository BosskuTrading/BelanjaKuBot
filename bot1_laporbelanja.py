import os
import logging
import base64
import io
from flask import Flask, request
from telegram import Bot, Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google.cloud import vision
from google.oauth2 import service_account
import datetime
import pytz
import gspread
from werkzeug.middleware.proxy_fix import ProxyFix

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT1_TOKEN = os.getenv("BOT1_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

if not BOT1_TOKEN or not SPREADSHEET_ID or not GOOGLE_CREDENTIALS_BASE64:
    raise Exception("Missing environment variables: BOT1_TOKEN, SPREADSHEET_ID, or GOOGLE_CREDENTIALS_BASE64")

# Load Google credentials
google_creds_bytes = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
creds = service_account.Credentials.from_service_account_info(
    eval(google_creds_bytes.decode("utf-8"))
)

# Google Sheets setup
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# Google Vision API
vision_client = vision.ImageAnnotatorClient(credentials=creds)

# Flask app
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

# Telegram Bot
application = Application.builder().token(BOT1_TOKEN).build()

MYTZ = pytz.timezone("Asia/Kuala_Lumpur")

def extract_text_from_image(img_bytes):
    image = vision.Image(content=img_bytes)
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

def log_to_sheets(chat_id, date, text):
    now = datetime.datetime.now(MYTZ)
    row = [str(chat_id), now.strftime("%Y-%m-%d %H:%M:%S"), text, date]
    sheet.append_row(row)

async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"👋 Hai {user_first_name}! Selamat datang ke *LaporBelanjaBot*\n\n"
             "📸 Sila hantar *gambar resit* ATAU taip *perbelanjaan* anda seperti:\n"
             "`RM5.30 Teh ais dan roti telur`\n\n"
             "Saya akan bantu rekodkan maklumat ini ke dalam laporan peribadi anda.",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    now = datetime.datetime.now(MYTZ).strftime("%Y-%m-%d")
    log_to_sheets(chat_id, now, text)
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Maklumat belanja berjaya direkodkan! Terima kasih kerana melaporkan 😊"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()

    await context.bot.send_message(chat_id=chat_id, text="🔍 Memproses imej... Sila tunggu sebentar.")

    text = extract_text_from_image(img_bytes)
    now = datetime.datetime.now(MYTZ).strftime("%Y-%m-%d")

    log_to_sheets(chat_id, now, text)
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Teks dari resit berjaya direkodkan!\n\n"
             "🧾 *Kandungan resit yang dibaca:*\n"
             f"```\n{text.strip()}\n```",
        parse_mode=ParseMode.MARKDOWN
    )

# Handlers
application.add_handler(CommandHandler("start", on_start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

# Webhook endpoint
@app.route(f"/{BOT1_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    logger.info(f"Update: {update.to_dict()}")
    application.update_queue.put_nowait(update)
    return "OK"

@app.route("/")
def index():
    return "LaporBelanjaBot is running."

if __name__ == "__main__":
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT1_TOKEN}"
    )
