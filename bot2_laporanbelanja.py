import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
import base64
import json

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT2_TOKEN = os.environ.get("BOT2_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")

if not all([BOT2_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_BASE64]):
    raise Exception("Sila setkan environment variables: BOT2_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_BASE64")

credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
credentials_dict = json.loads(credentials_json)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).sheet1  # Assuming first sheet

app = Flask(__name__)
bot = Bot(token=BOT2_TOKEN)

# Function to parse Google Sheet data to dict with user_id key
# We assume user_id is in a new column, otherwise will parse by username or chat_id stored in sheet by bot1
# For simplicity, here we assume user_id is stored in last column of each row (you must modify bot1 to save it)
# If not, just parse all and send combined report to all users who messaged bot2

def get_expenses():
    data = sheet.get_all_values()
    # header: Date, Time, Location, Items, Total Items, Total Amount, UserID (added in bot1)
    headers = data[0]
    rows = data[1:]
    expenses = []
    for row in rows:
        try:
            d = {
                "date": row[0],
                "time": row[1],
                "location": row[2],
                "items": row[3],
                "total_items": int(row[4]),
                "total_amount": float(row[5]),
                "user_id": int(row[6]) if len(row) > 6 else None
            }
            expenses.append(d)
        except Exception as e:
            logger.error(f"Error parsing row {row}: {e}")
    return expenses

def filter_expenses_by_user_and_period(expenses, user_id, start_date, end_date):
    filtered = []
    for e in expenses:
        if e['user_id'] != user_id:
            continue
        try:
            dt = datetime.strptime(e['date'], "%Y-%m-%d")
            if start_date <= dt <= end_date:
                filtered.append(e)
        except:
            continue
    return filtered

def format_report(expenses, period_name):
    if not expenses:
        return f"Tiada rekod belanja untuk {period_name}."
    total_amount = sum(e['total_amount'] for e in expenses)
    total_items = sum(e['total_items'] for e in expenses)
    locations = set(e['location'] for e in expenses)
    report_lines = [
        f"Laporan belanja untuk {period_name}:",
        f"Jumlah transaksi: {len(expenses)}",
        f"Jumlah item: {total_items}",
        f"Jumlah perbelanjaan: RM{total_amount:.2f}",
        f"Lokasi kedai: {', '.join(locations)}",
        "\nDetail transaksi:",
    ]
    for e in expenses:
        report_lines.append(f"{e['date']} - {e['location']} - RM{e['total_amount']:.2f} ({e['items']})")
    return "\n".join(report_lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Selamat datang ke *LaporanBelanjaBot*!\n\n"
        "Gunakan /laporan untuk dapatkan ringkasan belanja mingguan dan bulanan anda.\n"
        "Bot ini akan mengira berdasarkan data yang anda rekod melalui LaporBelanjaBot.\n"
        "Jika ada sebarang masalah, sila hubungi pentadbir."
    )
    await update.message.reply_markdown(text)

async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    expenses = get_expenses()

    today = datetime.today()
    # Mingguan (7 hari lalu)
    start_week = today - timedelta(days=7)
    weekly_expenses = filter_expenses_by_user_and_period(expenses, user_id, start_week, today)

    # Bulanan (1 bulan lalu)
    start_month = today - timedelta(days=30)
    monthly_expenses = filter_expenses_by_user_and_period(expenses, user_id, start_month, today)

    weekly_report = format_report(weekly_expenses, "7 hari lepas")
    monthly_report = format_report(monthly_expenses, "30 hari lepas")

    await update.message.reply_text(weekly_report)
    await update.message.reply_text(monthly_report)

@app.route(f'/{BOT2_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application = app.telegram_app
    application.update_queue.put(update)
    return jsonify({"status": "ok"})

async def set_webhook():
    url = os.environ.get("WEBHOOK_URL")
    if not url:
        logger.error("WEBHOOK_URL environment variable belum set")
        return
    webhook_url = f"{url}/{BOT2_TOKEN}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

def main():
    application = ApplicationBuilder().token(BOT2_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("laporan", laporan))

    app.telegram_app = application

    import asyncio
    asyncio.run(set_webhook())

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10001)))

if __name__ == "__main__":
    main()
