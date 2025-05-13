import os
import io
import json
import base64
import logging
import pytesseract
from PIL import Image
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters, CallbackContext
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from flask import Flask, request
import threading

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
async def start(update: Update, context: CallbackContext):
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
    try:
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()
        logger.info(f"Data for user {user_id} saved successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to save data to Google Sheets: {e}")
        raise

# Set up Flask app for webhook
app = Flask(__name__)

# Webhook endpoint for Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data(as_text=True)
    update = Update.de_json(json.loads(json_str), bot)
    dispatcher.process_update(update)
    return 'OK', 200

# Handle image message
async def handle_image(update: Update, context: CallbackContext):
    user = update.message.from_user
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_path = f"{user.id}_resit.jpg"
    
    # Download the image
    await file.download_to_drive(image_path)
    logger.info(f"Image downloaded: {image_path}")

    await update.message.reply_text("📸 Gambar diterima. Sedang memproses...")

    try:
        # Check image size and reduce if necessary
        image = Image.open(image_path)
        image.thumbnail((1024, 1024))  # Reduce size to avoid high memory usage
        image.save(image_path)

        # Extract text from the image
        text = extract_text(image_path)
        logger.info(f"Text extracted: {text}")

        # Parse extracted text and save to Google Sheets
        data = parse_receipt(text)
        save_to_sheet(user.id, data)
        await update.message.reply_text("✅ Maklumat berjaya disimpan ke Google Sheets.")
    except Exception as e:
        logger.error(f"❌ Gagal proses resit: {e}")
        await update.message.reply_text("❌ Maaf, resit tidak dapat diproses.")
    finally:
        # Clean up the image file after processing
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.info(f"Image file {image_path} deleted.")

# Main function to set up Telegram bot with webhook
def main():
    global bot, dispatcher

    bot = Bot(token=BOT1_TOKEN)
    dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

    # Set the webhook URL (replace with your Render URL)
    webhook_url = 'https://laporbelanjabot.onrender.com/webhook'
    bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to: {webhook_url}")

    # Add handlers to dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(filters.PHOTO, handle_image))

    # Run Flask in a separate thread to handle web requests
    thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    thread.start()

if __name__ == "__main__":
    main()
