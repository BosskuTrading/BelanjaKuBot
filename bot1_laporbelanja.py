import os
import logging
from datetime import datetime
from io import BytesIO

from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

import gspread
from google.oauth2.service_account import Credentials

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for ConversationHandler
NAMA_BARANG, LOKASI, BARANG_LAIN, RESIT = range(4)

# Load environment variables
BOT1_TOKEN = os.environ.get("BOT1_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")

if not all([BOT1_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_BASE64]):
    raise Exception("Sila setkan environment variables: BOT1_TOKEN, SHEET_ID, GOOGLE_CREDENTIALS_BASE64")

# Decode Google Credentials JSON from base64
import base64
import json
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
credentials_dict = json.loads(credentials_json)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).sheet1  # Assuming first sheet

# Create Flask app
app = Flask(__name__)
bot = Bot(token=BOT1_TOKEN)

# Folder to save receipt images
RECEIPT_FOLDER = "receipts"
os.makedirs(RECEIPT_FOLDER, exist_ok=True)

# Helper function to save receipt photo
def save_photo(photo_file, user_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{user_id}_{timestamp}.jpg"
    filepath = os.path.join(RECEIPT_FOLDER, filename)
    photo_file.download(filepath)
    return filepath

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Selamat datang ke *LaporBelanjaBot*!\n\n"
        "Anda boleh mula merekod belanja anda dengan mudah.\n"
        "Contoh: hantar maklumat seperti `Nasi Ayam RM10.50` dan saya akan bantu anda.\n"
        "Bot akan tanya lokasi kedai, barang lain dan minta upload gambar resit jika ada.\n\n"
        "Untuk batalkan proses, taip /cancel."
    )
    await update.message.reply_markdown(welcome_text)
    return NAMA_BARANG

# Receive first item and price
async def nama_barang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['items'] = []
    context.user_data['items'].append(text)
    await update.message.reply_text("Terima kasih! Sila berikan lokasi atau nama kedai:")
    return LOKASI

# Receive location / store name
async def lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text.strip()
    await update.message.reply_text(
        "Ada lagi barang yang anda beli? Sila senaraikan (contoh: Teh O RM2.00), atau taip 'Tiada'."
    )
    return BARANG_LAIN

# Receive additional items or finish
async def barang_lain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == 'tiada':
        await update.message.reply_text(
            "Jika ada gambar resit, sila upload sekarang, jika tidak taip 'Tiada'."
        )
        return RESIT
    else:
        context.user_data['items'].append(text)
        await update.message.reply_text("Ada lagi barang lain? Senaraikan atau taip 'Tiada'.")
        return BARANG_LAIN

# Receive photo or skip
async def resit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if update.message.photo:
        largest_photo = update.message.photo[-1]
        file = await largest_photo.get_file()
        filepath = save_photo(file, user_id)
        await update.message.reply_text("Gambar resit diterima dan disimpan.")
        context.user_data['receipt_path'] = filepath
    elif update.message.text and update.message.text.lower() == 'tiada':
        await update.message.reply_text("Tiada gambar resit. Rekod disimpan.")
        context.user_data['receipt_path'] = None
    else:
        await update.message.reply_text("Sila hantar gambar resit atau taip 'Tiada'.")
        return RESIT

    # Save record to Google Sheets
    try:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        location = context.user_data.get('location', '')
        items = context.user_data.get('items', [])
        total_items = len(items)

        # Calculate total amount from items text: parse numbers from text (e.g. 'Nasi Ayam RM10.50')
        total_amount = 0.0
        for item in items:
            # Find last number in string (simple)
            import re
            found = re.findall(r"RM(\d+\.?\d*)", item, re.IGNORECASE)
            if found:
                total_amount += float(found[-1])

        # Prepare row data for Google Sheets
        row = [
            date_str,
            time_str,
            location,
            " | ".join(items),
            total_items,
            f"{total_amount:.2f}"
        ]

        sheet.append_row(row)
        await update.message.reply_text("Rekod belanja berjaya disimpan ke Google Sheets. Terima kasih!")
    except Exception as e:
        logger.error(f"Error simpan ke Google Sheets: {e}")
        await update.message.reply_text("Maaf, berlaku masalah simpan data. Sila cuba lagi.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proses dibatalkan. Jika mahu mula semula, taip /start.")
    return ConversationHandler.END

# Telegram webhook route for Flask
@app.route(f'/{BOT1_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application = app.telegram_app
    application.update_queue.put(update)
    return jsonify({"status": "ok"})

# Setup webhook automatically (call once or via separate command)
async def set_webhook():
    url = os.environ.get("WEBHOOK_URL")  # e.g. https://yourdomain.com/{BOT1_TOKEN}
    if not url:
        logger.error("WEBHOOK_URL environment variable belum set")
        return
    webhook_url = f"{url}/{BOT1_TOKEN}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

def main():
    application = ApplicationBuilder().token(BOT1_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAMA_BARANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_barang)],
            LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, lokasi)],
            BARANG_LAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, barang_lain)],
            RESIT: [
                MessageHandler(filters.PHOTO, resit),
                MessageHandler(filters.TEXT & ~filters.COMMAND, resit),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    # Save application instance to Flask app for webhook
    app.telegram_app = application

    # Run webhook server on port 10000 (Render default)
    import asyncio

    # Run set_webhook asynchronously once before running app (optional)
    asyncio.run(set_webhook())

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
