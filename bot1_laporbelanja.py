import os
import io
import json
import base64
import logging
import pytesseract
from PIL import Image
from datetime import datetime
from flask import Flask, request

from telegram import Update, Bot
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from google.oauth2 import service_account
from googleapiclient.discovery import build

# === Logging ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Environment Variables ===
BOT1_TOKEN = os.getenv("BOT1_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://laporbelanjabot.onrender.com/webhook

if not all([BOT1_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_BASE64, WEBHOOK_URL]):
    raise EnvironmentError("Sila pastikan semua environment variables telah ditetapkan.")

# === Google Sheets Setup ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode('utf-8')
parsed_credentials = json.loads(credentials_json)
creds = service_account.Credentials.from_service_account_info(parsed_credentials, scopes=SCOPES)
sheet_service = build('sheets', 'v4', credentials=creds)
sheet = sheet_service.spreadsheets()

def get_user_range(user_id):
    return f"{user_id}!A:F"

# === Bot Command: /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hai! Hantar gambar resit anda dan saya akan simpan dalam Google Sheets.")

# === OCR & Parsing ===
def extract_text(image_path):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)
    return text

def parse_receipt(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    date, time, shop_name, total_amount = "", "", "", ""
    items = []

    for line in lines:
        l = line.lower()
        if "tarikh" in l or "date" in l:
            date = line
        elif "masa" in l or "time" in l:
            time = line
        elif "jumlah" in l or "total" in l:
            total_amount = line
        elif not shop_name:
            shop_name = line
        else:
            items.append(line)

    return {
        "date": date,
        "time": time,
        "shop_name": shop_name,
        "items": ', '.join(items),
        "total_amount": total_amount,
    }

def save_to_sheet(user_id, data):
    range_name = get_user_range(user_id)
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data["date"],
        data["time"],
        data["shop_name"],
        data["items"],
        data["total_amount"]
    ]
    sheet.values().append(
        spreadsheetId=SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()

# === Handle Image ===
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_path = f"{user.id}_resit.jpg"
    await file.download_to_drive(image_path)

    await update.message.reply_text("📸 Gambar diterima. Sedang memproses...")

    try:
        text = extract_text(image_path)
        data = parse_receipt(text)
        save_to_sheet(user.id, data)
        await update.message.reply_text("✅ Maklumat berjaya disimpan ke Google Sheets.")
    except Exception as e:
        logger.error(f"Gagal proses resit: {e}")
        await update.message.reply_text("❌ Maaf, resit tidak dapat diproses.")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

# === Flask App ===
app = Flask(__name__)
bot = Bot(token=BOT1_TOKEN)

# Telegram Application (shared across webhook & handlers)
telegram_app: Application = ApplicationBuilder().token(BOT1_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_image))

@app.route("/", methods=["GET"])
def index():
    return "🤖 LaporBelanjaBot is running (Webhook Mode)"

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    success = bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    return f"Webhook set: {success}"

@app.route("/webhook", methods=["POST"])
async def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, bot)
        await telegram_app.process_update(update)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return "ok"

# === Run Flask Server ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
