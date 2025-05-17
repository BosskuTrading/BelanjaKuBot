import os
import io
import json
import logging
import datetime
import asyncio
from flask import Flask, request, send_from_directory
from telegram import Update, Bot, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- Konfigurasi ---
BOT1_TOKEN = os.getenv("BOT1_TOKEN") or "YOUR_BOT1_TOKEN"
SHEET_ID = os.getenv("SHEET_ID") or "YOUR_SHEET_ID"
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")  # Base64 encoded service account json
RECEIPT_IMAGE_DIR = "receipts"  # Folder simpan gambar resit

if not os.path.exists(RECEIPT_IMAGE_DIR):
    os.makedirs(RECEIPT_IMAGE_DIR)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = Bot(token=BOT1_TOKEN)

# --- Google Sheets Setup ---
def get_gsheet_service():
    import base64
    cred_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode('utf-8')
    creds_dict = json.loads(cred_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

gsheet = get_gsheet_service()

# --- Google Sheet Helper ---
def append_row_to_sheet(row_data):
    """Append a row (list) to Google Sheet"""
    body = {'values': [row_data]}
    result = gsheet.values().append(
        spreadsheetId=SHEET_ID,
        range="Sheet1!A1",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    logger.info(f"Appended to sheet: {row_data}")
    return result

# --- Conversation States ---
ASK_LOCATION, ASK_MORE_ITEMS, ASK_UPLOAD_IMAGE = range(3)

# --- Temporary user session data store ---
user_sessions = {}

# --- Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Salam {user.first_name}! 👋\n"
        "Sila hantar maklumat belanja anda hari ini.\n"
        "Contoh: Nasi ayam RM10.50\n"
        "Atau hantar gambar resit untuk rekod."
    )
    user_sessions[user.id] = {
        "items": [],
        "location": None,
        "total_amount": 0.0,
        "chat_id": update.effective_chat.id,
        "date": datetime.date.today().strftime("%Y-%m-%d"),
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    return ASK_LOCATION

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # Check if user is in session
    session = user_sessions.get(user_id, None)
    if not session:
        await update.message.reply_text("Sila mula semula dengan /start")
        return ConversationHandler.END

    # Try parse simple input like "nasi ayam rm10.50"
    # We expect location if not present, so ask location
    session["last_item"] = text  # Save for later use if needed

    await update.message.reply_text(
        "Di mana lokasi/kedai anda beli barang ini?"
        "\nSila taip nama kedai atau lokasi."
    )
    return ASK_MORE_ITEMS

async def ask_more_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.text.strip()
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, None)

    if not session:
        await update.message.reply_text("Sila mula semula dengan /start")
        return ConversationHandler.END

    session["location"] = location
    # Simpan last item yang dihantar sebagai item pertama
    item = session.get("last_item", "")
    session["items"].append(item)

    await update.message.reply_text(
        "Ada barang lain yang anda mahu tambah? (Ya/Tidak)"
    )
    return ASK_UPLOAD_IMAGE

async def ask_upload_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, None)

    if not session:
        await update.message.reply_text("Sila mula semula dengan /start")
        return ConversationHandler.END

    if text in ("ya", "y", "yes"):
        await update.message.reply_text("Sila taip barang berikutnya dan jumlahnya:")
        return ASK_MORE_ITEMS
    elif text in ("tidak", "t", "no", "n"):
        await update.message.reply_text(
            "Sila hantar gambar resit (jika ada), atau taip 'Selesai' untuk simpan maklumat."
        )
        return ASK_UPLOAD_IMAGE
    elif text == "selesai":
        # Simpan ke Google Sheets
        return await save_data(update, context)
    else:
        # Check if this is image or text for more items
        if update.message.photo:
            # Process image receipt
            await save_receipt_image(update, context)
            await update.message.reply_text("Terima kasih! Data anda telah disimpan.")
            user_sessions.pop(user_id, None)
            return ConversationHandler.END
        else:
            # Treat as new item line
            session["items"].append(text)
            await update.message.reply_text("Ada barang lain? (Ya/Tidak)")
            return ASK_UPLOAD_IMAGE

async def save_receipt_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, None)
    if not session:
        await update.message.reply_text("Sila mula semula dengan /start")
        return ConversationHandler.END

    photo_file = await update.message.photo[-1].get_file()
    filename = f"{user_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = os.path.join(RECEIPT_IMAGE_DIR, filename)
    await photo_file.download_to_drive(filepath)
    logger.info(f"Saved receipt image to {filepath}")

    # NOTE: Anda boleh letak kod OCR di sini untuk auto-extract data dari gambar.

async def save_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, None)
    if not session:
        await update.message.reply_text("Sila mula semula dengan /start")
        return ConversationHandler.END

    # Kira jumlah item & jumlah belanja kasar
    total_items = len(session["items"])
    # Untuk demo, jumlah belanja anda boleh parse dari item (contoh 'nasi ayam rm10.50')
    total_amount = 0.0
    for item in session["items"]:
        # Cari pattern RM10.50 dalam text item
        import re
        m = re.search(r"rm\s?(\d+\.?\d*)", item, re.IGNORECASE)
        if m:
            total_amount += float(m.group(1))

    # Simpan data ke Google Sheets
    row = [
        session["date"],
        session["time"],
        session["location"],
        "; ".join(session["items"]),
        total_items,
        round(total_amount, 2),
        update.effective_user.full_name,
        user_id,
    ]

    append_row_to_sheet(row)
    await update.message.reply_text(
        f"Rekod perbelanjaan disimpan:\n"
        f"Tarikh: {session['date']}\n"
        f"Waktu: {session['time']}\n"
        f"Lokasi: {session['location']}\n"
        f"Items: {row[3]}\n"
        f"Jumlah items: {total_items}\n"
        f"Jumlah belanja: RM {round(total_amount,2)}"
    )
    user_sessions.pop(user_id, None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_sessions.pop(update.effective_user.id, None)
    await update.message.reply_text("Perbualan dibatalkan. Sila mula semula bila-bila masa dengan /start.")
    return ConversationHandler.END

# --- Setup Conversation Handler ---
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_LOCATION: [MessageHandler(filters.TEXT & (~filters.COMMAND), ask_location)],
        ASK_MORE_ITEMS: [MessageHandler(filters.TEXT & (~filters.COMMAND), ask_more_items)],
        ASK_UPLOAD_IMAGE: [
            MessageHandler(filters.PHOTO, save_receipt_image),
            MessageHandler(filters.TEXT & (~filters.COMMAND), ask_upload_image)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True,
)

application = Application.builder().token(BOT1_TOKEN).build()
application.add_handler(conv_handler)

# --- Flask webhook route ---
@app.route(f"/{BOT1_TOKEN}", methods=["POST"])
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
    return "LaporBelanjaBot running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
