import os
import base64
import datetime
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT2_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

def get_gsheet_service():
    creds_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
    creds = Credentials.from_service_account_info(eval(creds_json.decode("utf-8")),
                                                  scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build('sheets', 'v4', credentials=creds)
    return service

def get_all_expenses():
    service = get_gsheet_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Sheet1!A:G").execute()
    values = result.get('values', [])
    return values

def get_user_expenses(chat_id, start_date, end_date):
    expenses = []
    all_expenses = get_all_expenses()
    for row in all_expenses:
        try:
            row_date = datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
            row_chat_id = int(row[6])
            if row_chat_id == chat_id and start_date <= row_date <= end_date:
                expenses.append(row)
        except:
            continue
    return expenses

def sum_expenses(expenses):
    total = 0
    for row in expenses:
        try:
            total += float(row[5])
        except:
            continue
    return total

users_set = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_set.add(update.effective_chat.id)
    await update.message.reply_text(
        "Selamat datang ke LaporanBelanjaBot!\n"
        "Gunakan /laporanmingguan untuk laporan mingguan.\n"
        "Gunakan /laporanbulanan untuk laporan bulanan."
    )

async def laporan_mingguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    today = datetime.date.today()
    start_week = today - datetime.timedelta(days=today.weekday())
    end_week = start_week + datetime.timedelta(days=6)
    expenses = get_user_expenses(chat_id, start_week, end_week)
    total = sum_expenses(expenses)
    await update.message.reply_text(
        f"Laporan belanja anda dari {start_week} hingga {end_week}:\nJumlah perbelanjaan: RM {total:.2f}"
    )

async def laporan_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    today = datetime.date.today()
    start_month = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    end_month = next_month - datetime.timedelta(days=1)
    expenses = get_user_expenses(chat_id, start_month, end_month)
    total = sum_expenses(expenses)
    await update.message.reply_text(
        f"Laporan belanja anda bulan {today.month}/{today.year}:\nJumlah perbelanjaan: RM {total:.2f}"
    )

async def daily_report(context: CallbackContext):
    job = context.job
    chat_id = job.chat_id
    today = datetime.date.today()
    expenses = get_user_expenses(chat_id, today, today)
    total = sum_expenses(expenses)
    try:
        await context.bot.send_message(chat_id=chat_id, text=f"Laporan belanja harian untuk {today}:\nJumlah: RM {total:.2f}")
    except Exception as e:
        logger.error(f"Failed to send daily report to {chat_id}: {e}")

application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("laporanmingguan", laporan_mingguan))
application.add_handler(CommandHandler("laporanbulanan", laporan_bulanan))

# Atur jadual daily report pukul 8 pagi (UTC+8)
from telegram.ext import ApplicationBuilder, JobQueue

async def schedule_daily_reports(app: Application):
    # schedule daily reports for all users
    for user_chat_id in users_set:
        # 8am Malaysia time = 00:00 UTC (Malaysia is UTC+8)
        app.job_queue.run_daily(daily_report, time=datetime.time(hour=0, minute=0, second=0), chat_id=user_chat_id)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "OK"

if __name__ == "__main__":
    import asyncio
    port = int(os.environ.get("PORT", 10001))

    # Start app with scheduled jobs
    async def main():
        await schedule_daily_reports(application)
        await application.initialize()
        await application.start()
        app.run(host="0.0.0.0", port=port)

    asyncio.run(main())
