import os
import pytesseract
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from PIL import Image
import io
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

# Google Sheets API setup
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = os.getenv("SHEET_ID")

# Setup credentials & Sheets API
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

async def handle_receipt(update: Update, context):
    # Dapatkan gambar dari pengguna
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_path = await file.download()

    # Baca gambar dan extract teks menggunakan OCR
    image = Image.open(file_path)
    text = pytesseract.image_to_string(image)

    # Extract maklumat penting (ini boleh diubah berdasarkan format resit)
    lines = text.split('\n')
    date, time, store_name, items, total_amount = "", "", "", "", ""
    
    # Simpan maklumat resit dalam struktur (misalnya, kita anggap 1 item per resit)
    # Boleh buat extraction lebih kompleks
    for line in lines:
        if 'Date:' in line:
            date = line.split('Date:')[1].strip()
        if 'Store:' in line:
            store_name = line.split('Store:')[1].strip()
        if 'Items:' in line:
            items = line.split('Items:')[1].strip()
        if 'Total:' in line:
            total_amount = line.split('Total:')[1].strip()

    # Ambil chat_id pengguna
    chat_id = update.message.chat.id

    # Simpan data ke Google Sheets
    row = [date, time, store_name, "", items, 1, total_amount, chat_id, update.message.chat.username]
    sheet.values().append(
        spreadsheetId=SHEET_ID,
        range="Belanja!A:I",
        valueInputOption="RAW",
        body={"values": [row]}
    ).execute()

    await update.message.reply_text(f"Resit diterima dan data disimpan: {store_name} - {total_amount}.")

# Setup bot
app = ApplicationBuilder().token(os.getenv("BOT1_TOKEN")).build()
app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))

if __name__ == '__main__':
    app.run_polling()
