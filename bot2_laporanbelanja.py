import os
import json
import logging
import datetime
import base64
import asyncio
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT2_TOKEN = os.getenv("BOT2_TOKEN") or "YOUR_BOT2_TOKEN"
SHEET_ID = os.getenv("SHEET_ID") or "YOUR_SHEET_ID"
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = Bot(token=BOT2_TOKEN)
application = Application.builder().token(BOT2_TOKEN).build()

def get_gsheet_service():
    cred_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode('utf-8')
    creds_dict = json.loads(cred_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

gsheet = get_gsheet_service()

async def fetch_user_expenses(chat_id: int, start_date: str, end_date: str):
    # Fetch rows from Google Sheet for given user and date range
    sheet_data = gsheet.values().get(spreadsheetId=SHEET_ID, range="Sheet1!A2:H").execute()
    rows = sheet_data.get("values", [])
    filtered = []
    for r in rows:
        # Columns: date, time, location, items, total_items, total_amount, fullname, userid
        try:
            row_date = r[0]
            row_userid = int(r[7])
            if row_userid == chat_id and start_date <= row_date <= end_date:
                filtered.append(r)
        except Exception:
            continue
    return filtered

async def create_report(chat_id: int, report_type: str):
    today = datetime.date.today()
    if report_type == "harian":
        start_date = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = start_date
    elif report_type == "mingguan":
        start_date = (today - datetime.timedelta(days=today.weekday() + 7)).strftime("%Y-%m-%d")  # last Monday
        end_date = (today - datetime.timedelta(days=today.weekday() + 1)).strftime("%Y-%m-%d")    # last Sunday
    elif report_type == "bulanan":
        first_day_last_month = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        last_day_last_month = today.replace(day=1) - datetime.timedelta(days=1)
        start_date = first_day_last_month.strftime("%Y-%m-%d")
        end_date = last_day_last_month.strftime("%Y-%m-%d")
    else:
        return None

    expenses = await fetch_user_expenses(chat_id, start_date, end_date)
    if not expenses:
        return f"Tiada rekod perbelanjaan untuk {report_type} dari {start_date} hingga {end_date}."

    total_amount = 0.0
    total_items = 0
    details = []
    for r in expenses:
        details.append(f"{r[0]} {r[2]}: {r[3]} (RM{r[5]})")
        try:
            total_amount += float(r[5])
            total_items += int(r[4])
        except:
            pass

    report = (
        f"Laporan belanja {report_type} ({start_date} hingga {end_date}):\n\n"
        + "\n".join(details)
        + f"\n\nJumlah barang: {total_items}\nJumlah belanja: RM{total_amount:.2f}"
    )
    return report

async def send_report(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    report_type = job.name
    logger.info(f"Sending {report_type} report to {chat_id}")
    report_text = await create_report(chat_id, report_type)
    if report_text:
        try:
            await context.bot.send_message(chat_id=chat_id, text=report_text)
        except Exception as e:
            logger.error(f"Failed to send report to {chat_id}: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selamat datang ke LaporanBelanjaBot!\n"
        "Bot ini akan menghantar laporan harian, mingguan dan bulanan secara automatik pada pukul 8 pagi."
    )

async def laporan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sedang menyediakan laporan harian anda...")
    chat_id = update.effective_chat.id
    report = await create_report(chat_id, "harian")
    await update.message.reply_text(report)

application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("laporan", laporan_command))

# Scheduler untuk auto hantar laporan pukul 8 pagi setiap hari
scheduler = AsyncIOScheduler()

def schedule_reports_for_user(chat_id: int):
    # Buang kerja lama jika ada
    scheduler.remove_job(f"harian_{chat_id}", jobstore=None, silent=True)
    scheduler.add_job(
        send_report,
        "cron",
        hour=8,
        minute=0,
        id=f"harian_{chat_id}",
        name="harian",
        args=[],
        kwargs={"job": None},
        replace_existing=True,
        misfire_grace_time=300,
        kwargs={"chat_id": chat_id}
    )
    # Sama boleh tambah mingguan dan bulanan di sini (ikut jadual)

@app.route(f"/{BOT2_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        logger.info(f"Update received: {data}")
        update = Update.de_json(data, bot)
        asyncio.run(application.process_update(update))
        return "OK"
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return "Error", 500

@app.route("/")
def index():
    return "LaporanBelanjaBot running!"

if __name__ == "__main__":
    # Start scheduler
    scheduler.start()
    app.run(host="0.0.0.0", port=10001)
