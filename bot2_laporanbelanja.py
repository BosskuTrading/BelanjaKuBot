import os
import json
import base64
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler
import datetime
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Set timezone ke Malaysia
tz = pytz.timezone("Asia/Kuala_Lumpur")

# Ambil env vars
BOT_TOKEN = os.environ.get("BOT2_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
CREDENTIALS_B64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")

if not BOT_TOKEN or not SHEET_ID or not CREDENTIALS_B64:
    raise Exception("Sila setkan environment variables: BOT2_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_BASE64")

# Decode credential Google
creds_dict = json.loads(base64.b64decode(CREDENTIALS_B64).decode())
credentials = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
)

# Inisialisasi Google Sheets API
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# Setup Flask dan Telegram bot
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

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
        start = now - datetime.timedelta(days=now.weekday())  # start of week
    elif period == 'bulan':
        start = now.replace(day=1)  # start of month
    else:
        start = datetime.datetime.min.replace(tzinfo=tz)

    total = sum(e['total'] for e in expenses if e['date'] >= start)
    return total

# Handlers
def start(update: Update, context):
    update.message.reply_text("📊 Selamat datang ke *Laporan Belanja Bot*!\n\nGuna arahan berikut:\n/laporan - Lihat semua belanja\n/mingguan - Laporan minggu ini\n/bulanan - Laporan bulan ini", parse_mode="Markdown")

def laporan(update: Update, context):
    chat_id = update.message.chat_id
    expenses = get_user_expenses(chat_id)
    total = sum(e['total'] for e in expenses)
    update.message.reply_text(f"📋 Jumlah belanja keseluruhan: RM{total:.2f}")

def mingguan(update: Update, context):
    chat_id = update.message.chat_id
    expenses = get_user_expenses(chat_id)
    total = calculate_report(expenses, 'minggu')
    update.message.reply_text(f"🗓️ Jumlah belanja *minggu ini*: RM{total:.2f}", parse_mode="Markdown")

def bulanan(update: Update, context):
    chat_id = update.message.chat_id
    expenses = get_user_expenses(chat_id)
    total = calculate_report(expenses, 'bulan')
    update.message.reply_text(f"📆 Jumlah belanja *bulan ini*: RM{total:.2f}", parse_mode="Markdown")

# Setup webhook
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

# Root check
@app.route("/", methods=["GET", "HEAD"])
def index():
    return "Bot 2 Laporan Belanja Aktif!"

# Dispatcher setup
from telegram.ext import Dispatcher
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("laporan", laporan))
dispatcher.add_handler(CommandHandler("mingguan", mingguan))
dispatcher.add_handler(CommandHandler("bulanan", bulanan))

# Run app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
