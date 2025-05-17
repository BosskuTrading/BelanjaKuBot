import os
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import base64
import json
import asyncio

# --- Config ---
BOT2_TOKEN = os.getenv("BOT2_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

# --- Setup logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Setup Google Sheets ---
credentials_json = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_BASE64))
credentials = Credentials.from_service_account_info(credentials_json)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SHEET_ID).sheet1

# --- Setup Telegram Bot & Flask app ---
app = Flask(__name__)
bot = Bot(BOT2_TOKEN)
application = ApplicationBuilder().token(BOT2_TOKEN).build()

# --- Helper function to parse and sum data from sheet ---
def get_user_expenses(user_id: int, days_back: int):
    """Ambil jumlah perbelanjaan user_id dalam tempoh days_back hari."""
    records = sheet.get_all_records()
    total = 0.0
    cutoff = datetime.now() - timedelta(days=days_back)

    for row in records:
        try:
            row_user_id = int(row['user_id'])
            dt = datetime.strptime(row['datetime'], "%Y-%m-%d %H:%M:%S")
            amount = float(row['amount']) if 'amount' in row else 0
            if row_user_id == user_id and dt >= cutoff:
                total += amount
        except Exception:
            pass
    return total

# --- Bot commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Selamat datang ke LaporanBelanjaBot!\n\n"
        "Gunakan command:\n"
        "/mingguan - untuk laporan belanja seminggu\n"
        "/bulanan - untuk laporan belanja sebulan\n"
    )
    await update.message.reply_text(msg)

async def mingguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    total = get_user_expenses(user_id, 7)
    await update.message.reply_text(f"Jumlah belanja anda dalam 7 hari terakhir: RM{total:.2f}")

async def bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    total = get_user_expenses(user_id, 30)
    await update.message.reply_text(f"Jumlah belanja anda dalam 30 hari terakhir: RM{total:.2f}")

# Flask route untuk webhook
@app.route(f"/{BOT2_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.create_task(application.update_queue.put(update))
    return "OK"

# Route root untuk cek server hidup
@app.route("/")
def index():
    return "LaporanBelanjaBot is running"

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("mingguan", mingguan))
application.add_handler(CommandHandler("bulanan", bulanan))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10001"))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT2_TOKEN,
        webhook_url=f"https://YOUR_DOMAIN_OR_RENDER_URL/{BOT2_TOKEN}"
    )
