import os
import json
import base64
import datetime
import pytz
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Timezone
tz = pytz.timezone("Asia/Kuala_Lumpur")

# Env variables
BOT_TOKEN = os.environ.get("BOT2_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
CREDENTIALS_B64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")

if not BOT_TOKEN or not SHEET_ID or not CREDENTIALS_B64:
    raise Exception("Sila setkan environment variables: BOT2_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_BASE64")

# Google credentials
creds_dict = json.loads(base64.b64decode(CREDENTIALS_B64).decode())
credentials = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# Flask app
app = Flask(__name__)

# --- Utility Functions ---

def get_user_expenses(chat_id):
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Belanja!A2:H").execute()
    values = result.get('values', [])
    expenses = []
    for row in values:
        if len(row) >= 8 and row[1] == str(chat_id):
            try:
                date_obj = datetime.datetime.strptime(row[0], "%Y-%m-%d").replace(tzinfo=tz)
                expenses.append({
                    "date": date_obj,
                    "shop": row[4],
                    "total": float(row[7])
                })
            except:
                continue
    return expenses

def calculate_report(expenses, period='minggu'):
    now = datetime.datetime.now(tz)
    if period == 'minggu':
        start = now - datetime.timedelta(days=now.weekday())
    elif period == 'bulan':
        start = now.replace(day=1)
    else:
        start = datetime.datetime.min.replace(tzinfo=tz)
    total = sum(e['total'] for e in expenses if e['date'] >= start)
    return total

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Selamat datang ke *Laporan Belanja Bot*!\n\n"
        "Guna arahan berikut:\n"
        "/laporan - Lihat semua belanja\n"
        "/mingguan - Laporan minggu ini\n"
        "/bulanan - Laporan bulan ini", parse_mode="Markdown"
    )

async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    expenses = get_user_expenses(chat_id)
    total = sum(e['total'] for e in expenses)
    await update.message.reply_text(f"📋 Jumlah belanja keseluruhan: RM{total:.2f}")

async def mingguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    expenses = get_user_expenses(chat_id)
    total = calculate_report(expenses, 'minggu')
    await update.message.reply_text(f"🗓️ Jumlah belanja *minggu ini*: RM{total:.2f}", parse_mode="Markdown")

async def bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    expenses = get_user_expenses(chat_id)
    total = calculate_report(expenses, 'bulan')
    await update.message.reply_text(f"📆 Jumlah belanja *bulan ini*: RM{total:.2f}", parse_mode="Markdown")

# --- Telegram Application Setup ---

application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("laporan", laporan))
application.add_handler(CommandHandler("mingguan", mingguan))
application.add_handler(CommandHandler("bulanan", bulanan))

# --- Webhook route for Telegram ---

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
async def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return 'OK'

@app.route("/", methods=["GET", "HEAD"])
def index():
    return "Bot 2 (Laporan Belanja) sedang aktif."

if __name__ == "__main__":
    import asyncio
    port = int(os.environ.get("PORT", 10000))
    asyncio.run(app.run_task(host="0.0.0.0", port=port))
