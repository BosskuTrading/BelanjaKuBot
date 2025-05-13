import os
import io
import json
import base64
import logging
import pytesseract
from PIL import Image
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT1_TOKEN = os.getenv("BOT1_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

if not GOOGLE_CREDENTIALS_BASE64:
    raise ValueError("Environment variable GOOGLE_CREDENTIALS_BASE64 tidak diset!")

# Decode Base64 and load credentials as dictionary
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode('utf-8')
credentials_io = io.StringIO(credentials_json)
parsed_credentials = json.load(credentials_io)

# Create credentials object
creds = service_account.Credentials.from_service_account_info(parsed_credentials, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Format Google Sheets range by chat_id
def get_user_range(user_id):
    return f"{user_id}!A:F"

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hai! Hantar gambar resit anda dan saya akan simpan dalam Google Sheets.")

# Extract text from image
def extract_text(image_path):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)
    return text

# Parse receipt text
def parse_receipt(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    date, time, shop_name, total_amount = "", "", "", ""
    items = []

    for line in lines:
        l = line.lower()
        if "tarikh" in l or "date" in l:
            date = line
        elif "masa" in l or "time" in l:
            time = line
        elif "jumlah" in l or "total" in l:
            total_amount = line
        elif not shop_name:
            shop_name = line
        else:
            items.append(line)

    return {
        "date": date,
        "time": time,
        "shop_name": shop_name,
        "items": ', '.join(items),
        "total_amount": total_amount,
    }

# Save data to Google Sheets
def save_to_sheet(user_id, data):
    range_name = get_user_range(user_id)
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data["date"],
        data["time"],
        data["shop_name"],
        data["items"],
        data["total_amount"]
    ]
    sheet.values().append(
        spreadsheetId=SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()

# Handle image message
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_path = f"{user.id}_resit.jpg"
    await file.download_to_drive(image_path)

    await update.message.reply_text("📸 Gambar diterima. Sedang memproses...")

    try:
        text = extract_text(image_path)
        data = parse_receipt(text)
        save_to_sheet(user.id, data)
        await update.message.reply_text("✅ Maklumat berjaya disimpan ke Google Sheets.")
    except Exception as e:
        logger.error(f"❌ Gagal proses resit: {e}")
        await update.message.reply_text("❌ Maaf, resit tidak dapat diproses.")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

# Main function
def main():
    app = Application.builder().token(BOT1_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.run_polling()

if __name__ == "__main__":
    main()
