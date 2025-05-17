import os
import base64
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIG ---
BOT_TOKEN = os.getenv('BOT2_TOKEN')
GOOGLE_CREDENTIALS_BASE64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
SHEET_ID = '1h2br8RSuvuNVydz-4sKXalziottO4QHwtSVP8v1RECQ'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Google Sheets Setup ---
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
credentials = service_account.Credentials.from_service_account_info(json.loads(credentials_json), scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# --- Flask App ---
app = Flask(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "Salam! Saya LaporanBelanjaBot.\n\n"\
                   "Gunakan /laporan_mingguan untuk dapatkan laporan belanja minggu ini.\n"\
                   "Gunakan /laporan_bulanan untuk dapatkan laporan belanja bulan ini."
    await update.message.reply_text(welcome_text)

def fetch_expenses():
    """Fetch all expense data from Google Sheets"""
    result = sheet.values().get(spreadsheetId=SHEET_ID, range='Sheet1!A2:G').execute()
    rows = result.get('values', [])
    return rows

def filter_by_date(rows, start_date, end_date):
    """Filter rows by date range"""
    filtered = []
    for row in rows:
        try:
            date_str = row[0]
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            if start_date <= dt <= end_date:
                filtered.append(row)
        except Exception:
            continue
    return filtered

def summarize_expenses(rows):
    """Summarize total expenses"""
    total = 0.0
    for r in rows:
        try:
            amount = float(r[5])
            total += amount
        except Exception:
            pass
    return total, len(rows)

async def laporan_mingguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now()
    start_week = today - timedelta(days=today.weekday())  # Monday this week
    end_week = start_week + timedelta(days=6)
    
    rows = fetch_expenses()
    filtered = filter_by_date(rows, start_week, end_week)
    total, count = summarize_expenses(filtered)
    
    reply = (
        f"Laporan Mingguan ({start_week.strftime('%Y-%m-%d')} hingga {end_week.strftime('%Y-%m-%d')}):\n"
        f"Jumlah transaksi: {count}\n"
        f"Jumlah perbelanjaan: RM {total:.2f}"
    )
    await update.message.reply_text(reply)

async def laporan_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now()
    start_month = today.replace(day=1)
    # Get last day of month
    if today.month == 12:
        end_month = today.replace(day=31)
    else:
        end_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
    rows = fetch_expenses()
    filtered = filter_by_date(rows, start_month, end_month)
    total, count = summarize_expenses(filtered)
    
    reply = (
        f"Laporan Bulanan ({start_month.strftime('%Y-%m-%d')} hingga {end_month.strftime('%Y-%m-%d')}):\n"
        f"Jumlah transaksi: {count}\n"
        f"Jumlah perbelanjaan: RM {total:.2f}"
    )
    await update.message.reply_text(reply)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook_handler():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return 'OK'

async def set_webhook():
    webhook_url = f"https://laporanbelanjabot.onrender.com/{BOT_TOKEN}"
    await application.bot.set_webhook(webhook_url)

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('laporan_mingguan', laporan_mingguan))
    application.add_handler(CommandHandler('laporan_bulanan', laporan_bulanan))
    
    import asyncio
    asyncio.run(set_webhook())

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
