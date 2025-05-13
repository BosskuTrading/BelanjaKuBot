import os
import io
import base64
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment Variables
BOT2_TOKEN = os.getenv("BOT2_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

# Google Sheets Setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

if not GOOGLE_CREDENTIALS_BASE64:
    raise ValueError("Environment variable 'GOOGLE_CREDENTIALS_BASE64' tidak diset!")

# Decode Base64 dari environment
try:
    credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode('utf-8')
except Exception as e:
    raise ValueError("❌ Gagal decode GOOGLE_CREDENTIALS_BASE64. Sila pastikan ia adalah Base64 yang sah.") from e

credentials_io = io.BytesIO(credentials_json.encode('utf-8'))

# Buat credentials object
creds = service_account.Credentials.from_service_account_file(
    credentials_io, scopes=SCOPES
)

# Setup Sheets API client
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Fungsi bantu: tapis baris ikut tarikh
def filter_by_date(rows, start_date):
    total = 0.0
    for row in rows:
        if len(row) < 6:
            continue
        try:
            row_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            if row_date >= start_date:
                total += float(row[5])
        except Exception:
            continue
    return total

# Jana laporan untuk user
def generate_report(user_id):
    range_name = f"{user_id}!A:F"
    result = sheet.values().get(spreadsheetId=SHEET_ID, range=range_name).execute()
    values = result.get('values', [])

    now = datetime.now()
    last_week = now - timedelta(days=7)
    last_month = now - timedelta(days=30)

    total_week = filter_by_date(values, last_week)
    total_month = filter_by_date(values, last_month)

    report = (
        f"📊 *Laporan Belanja Anda*\n\n"
        f"🗓️ Minggu lepas: RM {total_week:.2f}\n"
        f"📅 Bulan ini: RM {total_month:.2f}"
    )
    return report

# Command /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hai! Saya bot laporan. Guna /laporan untuk lihat ringkasan belanja mingguan & bulanan.")

# Command /laporan
async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        report = generate_report(user_id)
        await update.message.reply_text(report, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Gagal hasilkan laporan: {e}")
        await update.message.reply_text("❌ Gagal hasilkan laporan. Pastikan anda telah hantar resit kepada Bot 1.")

# Main
def main():
    app = Application.builder().token(BOT2_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("laporan", laporan))
    app.run_polling()

if __name__ == "__main__":
    main()
