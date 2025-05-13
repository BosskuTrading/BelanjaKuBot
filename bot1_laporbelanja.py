import os
import io
import base64
import logging
import pytesseract
from PIL import Image
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Get environment variables
BOT1_TOKEN = os.getenv("BOT1_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

# Google Sheets API setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

if not GOOGLE_CREDENTIALS_BASE64:
    raise ValueError("Environment variable GOOGLE_CREDENTIALS_BASE64 tidak diset.")

# Decode credentials.json dari base64
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode('utf-8')
credentials_io = io.BytesIO(credentials_json.encode('utf-8'))

# Load credentials dari memory (tanpa fail)
creds = service_account.Credentials.from_service_account_file(
    credentials_io, scopes=SCOPES
)

service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Define Google Sheets range format
def get_user_range(user_id):
    return f"{user_id}!A:F"

# Define /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hai! Hantar gambar resit anda dan saya akan rekodkan dalam Google Sheets.")

# Extract text from image
def extract_text(image_path):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)
    return text

# Parse receipt text to structured data (simple version)
def parse_receipt(text):
    lines = text.splitlines()
    lines = [line.strip() for line in lines if line.strip()]

    date = ""
    location = ""
    time = ""
    shop_name = ""
    items = []
    total_amount = ""

    for line in lines:
        if "tarikh" in line.lower() or "date" in line.lower():
            date = line
        elif "masa" in line.lower() or "time" in line.lower():
            time = line
        elif "jumlah" in line.lower() or "total" in line.lower():
            total_amount = line
        elif not shop_name:
            shop_name = line
        else:
            items.append(line)

    return {
        "date": date,
        "time": time,
        "location": location,
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

# Handle image messages
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
        logger.error(f"Error processing receipt: {e}")
        await update.message.reply_text("❌ Gagal memproses resit. Sila cuba lagi.")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

# Main entry
def main():
    app = Application.builder().token(BOT1_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    app.run_polling()

if __name__ == "__main__":
    main()
