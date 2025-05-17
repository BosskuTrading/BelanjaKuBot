import os
import base64
import json
import datetime
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import asyncio

# ======= AMBIL ENVIRONMENT VARIABLE ===========
BOT2_TOKEN = os.getenv('BOT2_TOKEN')
SHEET_ID = os.getenv('SHEET_ID')
GOOGLE_CREDENTIALS_BASE64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')

if not (BOT2_TOKEN and SHEET_ID and GOOGLE_CREDENTIALS_BASE64):
    raise Exception("Sila setkan environment variables: BOT2_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_BASE64")

# ======= DECODE GOOGLE CREDENTIALS JSON =======
credentials_info = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_BASE64))
credentials = Credentials.from_service_account_info(credentials_info)

# ======= GOOGLE SHEETS API CLIENT ===========
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# ======= FLASK & TELEGRAM BOT SETUP =========
app = Flask(__name__)
application = ApplicationBuilder().token(BOT2_TOKEN).build()

# ======= COMMAND HANDLERS ===========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selamat datang ke LaporanBelanjaBot!\n"
        "Gunakan /laporan untuk dapatkan ringkasan perbelanjaan mingguan dan bulanan anda."
    )

def get_user_expenses(chat_id):
    # Tarik semua data dari Sheet (anggap sheet ada kolum: chat_id | date(YYYY-MM-DD) | shop | total_amount)
    RANGE = "Sheet1!A2:D"
    result = sheet.values().get(spreadsheetId=SHEET_ID, range=RANGE).execute()
    rows = result.get('values', [])
    user_data = []
    for row in rows:
        if len(row) < 4:
            continue
        row_chat_id, date_str, shop, amount_str = row
        if str(row_chat_id) == str(chat_id):
            try:
                total_amount = float(amount_str)
                user_data.append({
                    'date': date_str,
                    'shop': shop,
                    'total_amount': total_amount
                })
            except:
                continue
    return user_data

async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    data = get_user_expenses(chat_id)
    if not data:
        await update.message.reply_text("Maaf, tiada rekod perbelanjaan anda ditemui.")
        return

    today = datetime.date.today()
    one_week_ago = today - datetime.timedelta(days=7)
    one_month_ago = today - datetime.timedelta(days=30)

    weekly_total = sum(d['total_amount'] for d in data if datetime.datetime.strptime(d['date'], '%Y-%m-%d').date() >= one_week_ago)
    monthly_total = sum(d['total_amount'] for d in data if datetime.datetime.strptime(d['date'], '%Y-%m-%d').date() >= one_month_ago)

    message = (
        f"Laporan Perbelanjaan Anda:\n\n"
        f"Jumlah perbelanjaan minggu lalu: RM {weekly_total:.2f}\n"
        f"Jumlah perbelanjaan bulan ini: RM {monthly_total:.2f}\n\n"
        f"Terima kasih menggunakan LaporBelanjaBot!"
    )
    await update.message.reply_text(message)

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("laporan", laporan))

# ===== FLASK WEBHOOK ROUTE =====
@app.route(f'/{BOT2_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return 'ok'

@app.route('/')
def index():
    return "Bot2 LaporanBelanjaBot is running."

# ===== MAIN RUN =====
if __name__ == "__main__":
    app.run(port=10001)
