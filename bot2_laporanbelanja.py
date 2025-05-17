import os
import json
import logging
import datetime
from flask import Flask, request, abort
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, filters
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from apscheduler.schedulers.background import BackgroundScheduler

# --- CONFIG ---
TOKEN_BOT2 = os.getenv("TOKEN_BOT2") or "YOUR_BOT2_TOKEN_HERE"
SHEET_ID = os.getenv("SHEET_ID") or "1h2br8RSuvuNVydz-4sKXalziottO4QHwtSVP8v1RECQ"

GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not GOOGLE_CREDENTIALS_JSON:
    raise RuntimeError("Missing Google Credentials in GOOGLE_CREDENTIALS_JSON env var")

credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
credentials = Credentials.from_service_account_info(credentials_info)
sheets_service = build('sheets', 'v4', credentials=credentials)

bot = Bot(token=TOKEN_BOT2)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Helpers ---

def read_sheet_data():
    """
    Read all data from Sheet1 in Google Sheets
    Returns list of rows (each row is list of values)
    """
    try:
        sheet = sheets_service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SHEET_ID, range="Sheet1!A:G").execute()
        values = result.get('values', [])
        return values
    except Exception as e:
        logger.error(f"Failed to read Google Sheets: {e}")
        return []

def filter_data_by_chat_id(data, chat_id):
    """
    Filter rows with matching chat_id (column G)
    """
    return [row for row in data if len(row) >= 7 and row[6] == str(chat_id)]

def sum_expenses(data):
    """
    Sum total amount from data rows (column F)
    """
    total = 0.0
    for row in data:
        try:
            total += float(row[5])
        except Exception:
            pass
    return total

def count_items(data):
    """
    Sum total items count from data rows (column E)
    """
    total_items = 0
    for row in data:
        try:
            total_items += int(row[4])
        except Exception:
            pass
    return total_items

def build_report_text(data, period_desc):
    """
    Build readable text report from data rows for given period description
    """
    if not data:
        return f"Tidak ada rekod belanja untuk {period_desc}."

    total_items = count_items(data)
    total_amount = sum_expenses(data)

    lines = [f"Laporan Belanja {period_desc}:\n"]
    for row in data:
        date = row[0]
        time = row[1]
        shop = row[2]
        items = row[3]
        amount = row[5]
        lines.append(f"- {date} {time}, {shop}, RM{amount}")
    lines.append(f"\nJumlah Item: {total_items}")
    lines.append(f"Jumlah Perbelanjaan: RM{total_amount:.2f}")

    return "\n".join(lines)

def filter_data_by_date_range(data, start_date, end_date):
    """
    Filter rows by date range (inclusive)
    Date format expected: 'YYYY-MM-DD'
    """
    filtered = []
    for row in data:
        if len(row) < 1:
            continue
        try:
            row_date = datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
            if start_date <= row_date <= end_date:
                filtered.append(row)
        except Exception:
            continue
    return filtered

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "Selamat datang ke bot laporan belanja!\n"
            "Gunakan command:\n"
            "/laporan_harian - Laporan belanja hari ini\n"
            "/laporan_mingguan - Laporan minggu ini\n"
            "/laporan_bulanan - Laporan bulan ini"
        )
    )

async def laporan_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = read_sheet_data()
    data_user = filter_data_by_chat_id(data, chat_id)

    today = datetime.date.today()
    filtered = filter_data_by_date_range(data_user, today, today)
    report_text = build_report_text(filtered, "hari ini")

    await context.bot.send_message(chat_id=chat_id, text=report_text)

async def laporan_mingguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = read_sheet_data()
    data_user = filter_data_by_chat_id(data, chat_id)

    today = datetime.date.today()
    start_week = today - datetime.timedelta(days=today.weekday())  # Monday
    end_week = start_week + datetime.timedelta(days=6)
    filtered = filter_data_by_date_range(data_user, start_week, end_week)
    report_text = build_report_text(filtered, "minggu ini")

    await context.bot.send_message(chat_id=chat_id, text=report_text)

async def laporan_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = read_sheet_data()
    data_user = filter_data_by_chat_id(data, chat_id)

    today = datetime.date.today()
    start_month = today.replace(day=1)
    # Calculate last day of month
    if today.month == 12:
        end_month = today.replace(year=today.year+1, month=1, day=1) - datetime.timedelta(days=1)
    else:
        end_month = today.replace(month=today.month+1, day=1) - datetime.timedelta(days=1)

    filtered = filter_data_by_date_range(data_user, start_month, end_month)
    report_text = build_report_text(filtered, "bulan ini")

    await context.bot.send_message(chat_id=chat_id, text=report_text)

# --- Scheduled Task ---

async def send_daily_report():
    """
    Scheduled daily report send at 8am to all distinct chat_ids found in sheet
    """
    data = read_sheet_data()
    chat_ids = set(row[6] for row in data if len(row) >= 7)

    today = datetime.date.today() - datetime.timedelta(days=1)  # report for yesterday
    for chat_id in chat_ids:
        try:
            data_user = filter_data_by_chat_id(data, chat_id)
            filtered = filter_data_by_date_range(data_user, today, today)
            if not filtered:
                continue
            report_text = build_report_text(filtered, f"hari semalam ({today.isoformat()})")
            await bot.send_message(chat_id=int(chat_id), text=report_text)
        except Exception as e:
            logger.error(f"Failed send daily report to {chat_id}: {e}")

# --- Flask Webhook Handler ---

@app.route(f"/{TOKEN_BOT2}", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        application.update_queue.put(update)
        return "OK"
    else:
        abort(405)

# --- Main ---

if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN_BOT2).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("laporan_harian", laporan_harian))
    application.add_handler(CommandHandler("laporan_mingguan", laporan_mingguan))
    application.add_handler(CommandHandler("laporan_bulanan", laporan_bulanan))

    # Setup scheduler to send daily report at 8 AM server time
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: application.create_task(send_daily_report()),
        trigger="cron",
        hour=8,
        minute=0,
        second=0,
        timezone="Asia/Kuala_Lumpur"  # Adjust timezone accordingly
    )
    scheduler.start()

    # Run Flask app on port 5000 or Render port
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
