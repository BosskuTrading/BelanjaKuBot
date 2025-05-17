import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Config ---
BOT1_TOKEN = os.getenv("BOT1_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
UPLOAD_FOLDER = "./uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Setup logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Setup Google Sheets ---
import base64
import json
credentials_json = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_BASE64))
credentials = Credentials.from_service_account_info(credentials_json)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SHEET_ID).sheet1

# --- Setup Telegram Bot & Flask app ---
app = Flask(__name__)
bot = Bot(BOT1_TOKEN)
application = ApplicationBuilder().token(BOT1_TOKEN).build()

# --- Bot commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "Selamat datang ke LaporBelanjaBot!\n\n"
        "Kirimkan butiran belanja anda seperti:\n"
        "- Hantar teks (contoh: nasi ayam 10.50)\n"
        "- Atau gambar resit.\n"
        "Bot akan simpan rekod anda secara automatik."
    )
    await update.message.reply_text(welcome_msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "Cara guna bot ini:\n"
        "1. Hantar teks contoh: 'Nasi ayam 10.50'\n"
        "2. Bot akan tanya lokasi kedai dan item lain jika mahu.\n"
        "3. Atau terus hantar gambar resit.\n"
        "4. Bot akan simpan maklumat ke Google Sheets."
    )
    await update.message.reply_text(help_msg)

# Simpan teks belanja user ke Google Sheets (contoh mudah)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Simpan row: user_id, datetime, text
    sheet.append_row([user.id, now, text])

    await update.message.reply_text("Terima kasih! Maklumat belanja anda telah direkod.")

# Simpan gambar resit
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    photos = update.message.photo
    photo_file = photos[-1].get_file()
    filename = f"{user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    await photo_file.download_to_drive(filepath)

    await update.message.reply_text("Gambar resit diterima dan disimpan. Terima kasih!")

# Flask route untuk webhook
@app.route(f"/{BOT1_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.create_task(application.update_queue.put(update))
    return "OK"

# Route root untuk cek server hidup
@app.route("/")
def index():
    return "LaporBelanjaBot is running"

# Tambah handler ke aplikasi telegram
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT1_TOKEN,
        webhook_url=f"https://YOUR_DOMAIN_OR_RENDER_URL/{BOT1_TOKEN}"
    )
