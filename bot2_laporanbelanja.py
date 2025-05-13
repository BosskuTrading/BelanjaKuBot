from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os

# Google Sheets API setup
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = os.getenv("SHEET_ID")

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

async def report_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Belanja!A:I").execute()
    values = result.get('values', [])
    
    # Filter data untuk pengguna yang meminta laporan
    total = 0.0
    for row in values:
        if len(row) > 7 and row[7] == str(chat_id):  # Pastikan `chat_id` ada pada kolum 7
            total += float(row[6])  # Kolum 6 adalah jumlah perbelanjaan
    await update.message.reply_text(f"Jumlah belanja anda minggu ini: RM {total:.2f}")

async def report_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Belanja!A:I").execute()
    values = result.get('values', [])
    
    # Filter data untuk pengguna yang meminta laporan
    total = 0.0
    for row in values:
        if len(row) > 7 and row[7] == str(chat_id):  # Pastikan `chat_id` ada pada kolum 7
            total += float(row[6])  # Kolum 6 adalah jumlah perbelanjaan
    await update.message.reply_text(f"Jumlah belanja anda bulan ini: RM {total:.2f}")

# Setup bot
app = ApplicationBuilder().token(os.getenv("BOT2_TOKEN")).build()
app.add_handler(CommandHandler("minggu", report_week))
app.add_handler(CommandHandler("bulan", report_month))

if __name__ == '__main__':
    app.run_polling()
