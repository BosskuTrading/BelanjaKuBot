import os
import logging
import asyncio
import threading
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import base64
import json
import re

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("bot1_laporbelanja")

# ====== Environment variables ======
BOT_TOKEN = os.getenv("BOT1_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

if not BOT_TOKEN or not SPREADSHEET_ID or not GOOGLE_CREDENTIALS_BASE64:
    logger.error("Missing one or more environment variables: BOT1_TOKEN, SPREADSHEET_ID, GOOGLE_CREDENTIALS_BASE64")
    raise RuntimeError("Missing environment variables.")

# ====== Google Sheets Setup ======
credentials_dict = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_BASE64))
credentials = Credentials.from_service_account_info(credentials_dict)
sheet_service = build("sheets", "v4", credentials=credentials)
sheet = sheet_service.spreadsheets()

def append_to_sheet(row):
    try:
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Sheet1!A:F",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        logger.info(f"Appended row: {row}")
    except Exception as e:
        logger.error(f"Error appending to sheet: {e}")

# ====== OCR / Parsing Dummy Functions ======
def perform_ocr(image_bytes):
    # Placeholder dummy OCR text - replace with actual OCR call like Google Vision API
    return "12/05/2025 MyKedai RM23.50"

def parse_date(text):
    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    return m.group(1) if m else None

def parse_amount(text):
    m = re.search(r"RM?(\d+[\.,]?\d*)", text, re.IGNORECASE)
    if m:
        return m.group(1).replace(",", ".")
    return None

# ====== Conversation states ======
CHOOSING, MANUAL_INPUT = range(2)

# ====== Telegram Bot Setup ======
application = ApplicationBuilder().token(BOT_TOKEN).build()

CHOICES = [["Taip Belanja", "Hantar Resit"]]

# ---- Handlers ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or "Sahabat"
    welcome_msg = (
        f"Hai {user_first_name}! 👋\n\n"
        "Saya adalah pembantu belanja anda.\n"
        "Boleh pilih cara nak rekod belanja anda hari ini:\n"
        "👉 Taip belanja secara manual\n"
        "👉 Hantar gambar resit pembelian\n\n"
        "Sila pilih salah satu pilihan di bawah."
    )
    reply_markup = ReplyKeyboardMarkup(CHOICES, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup)
    return CHOOSING

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "Cara guna bot ini:\n"
        "1. Pilih 'Taip Belanja' untuk masukkan maklumat belanja secara manual.\n"
        "2. Pilih 'Hantar Resit' untuk hantar gambar resit pembelian.\n"
        "3. Saya akan rekod maklumat anda ke Google Sheets.\n"
        "4. Gunakan /status untuk semak berapa banyak resit yang anda dah hantar.\n"
        "5. Gunakan /ping untuk semak sama ada bot ini sedang aktif.\n"
        "6. Gunakan /cancel untuk batalkan input semasa.\n\n"
        "Kalau ada sebarang masalah, sila hubungi admin ya."
    )
    await update.message.reply_text(help_msg, reply_markup=ReplyKeyboardRemove())

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot sedang online dan sedia membantu anda! ✅")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        range_ = "Sheet1!A:A"
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_).execute()
        values = result.get("values", [])
        count = sum(1 for row in values if row and row[0] == str(chat_id))
        await update.message.reply_text(
            f"Anda telah menghantar {count} resit atau belanja ke bot ini. Terima kasih! 👍"
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        await update.message.reply_text(
            "Maaf, saya tidak dapat semak status anda sekarang."
        )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Input dibatalkan. Taip /start untuk mula semula.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "taip belanja" in text:
        await update.message.reply_text(
            "Sila taip maklumat belanja anda dalam format mudah seperti:\n\n"
            "Tarikh(dd/mm/yyyy) NamaKedai Jumlah\n\n"
            "Contoh:\n12/05/2025 MyKedai 23.50",
            reply_markup=ReplyKeyboardRemove(),
        )
        return MANUAL_INPUT
    elif "hantar resit" in text:
        await update.message.reply_text(
            "Baik! Sila hantar gambar resit pembelian anda sekarang.",
            reply_markup=ReplyKeyboardRemove(),
        )
        # Terus keluar conversation, tunggu photo handler
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Maaf, saya tidak faham pilihan anda. Sila pilih 'Taip Belanja' atau 'Hantar Resit'.",
            reply_markup=ReplyKeyboardMarkup(CHOICES, one_time_keyboard=True, resize_keyboard=True),
        )
        return CHOOSING

async def manual_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split()
    if len(parts) < 3:
        await update.message.reply_text(
            "Format tidak betul. Sila taip semula dengan format:\n"
            "Tarikh(dd/mm/yyyy) NamaKedai Jumlah\nContoh: 12/05/2025 MyKedai 23.50"
        )
        return MANUAL_INPUT

    tarikh, jumlah = parts[0], parts[-1]
    nama_kedai = " ".join(parts[1:-1])

    try:
        datetime.strptime(tarikh, "%d/%m/%Y")
    except ValueError:
        await update.message.reply_text(
            "Tarikh tidak sah. Sila guna format dd/mm/yyyy, contoh: 12/05/2025"
        )
        return MANUAL_INPUT

    try:
        jumlah_val = float(jumlah)
    except ValueError:
        await update.message.reply_text(
            "Jumlah tidak sah. Sila taip nombor seperti 23.50"
        )
        return MANUAL_INPUT

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [str(update.effective_chat.id), now_str, tarikh, nama_kedai, f"{jumlah_val:.2f}", "Manual Input"]
    append_to_sheet(row)

    await update.message.reply_text(
        "✅ Maklumat belanja anda telah direkodkan!\n"
        f"🗓 Tarikh: {tarikh}\n"
        f"🏪 Kedai: {nama_kedai}\n"
        f"💰 Jumlah: RM {jumlah_val:.2f}\n\n"
        "Terima kasih kerana menggunakan bot ini.\n"
        "Taip /status untuk semak jumlah belanja anda.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = update.message.photo
    if not photos:
        await update.message.reply_text(
            "Maaf, gambar tidak ditemui. Sila cuba hantar semula."
        )
        return

    photo_file = photos[-1]
    file = await context.bot.get_file(photo_file.file_id)
    image_bytes = await file.download_as_bytearray()
    image_bytes = bytes(image_bytes)

    # Dummy OCR call
    ocr_text = perform_ocr(image_bytes)
    tarikh = parse_date(ocr_text) or datetime.now().strftime("%d/%m/%Y")
    jumlah = parse_amount(ocr_text) or "0.00"
    nama_kedai = "Resit OCR"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [str(update.effective_chat.id), now_str, tarikh, nama_kedai, f"{float(jumlah):.2f}", "OCR Photo"]
    append_to_sheet(row)

    await update.message.reply_text(
        "✅ Resit gambar anda telah diterima dan direkodkan.\n"
        f"🗓 Tarikh: {tarikh}\n"
        f"🏪 Kedai: {nama_kedai}\n"
        f"💰 Jumlah: RM {float(jumlah):.2f}\n\n"
        "Terima kasih kerana menggunakan bot ini.",
    )

# ====== Conversation Handler setup ======
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choice_handler)],
        MANUAL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_input_handler)],
    },
    fallbacks=[CommandHandler("cancel", cancel_command)],
)

# Add all handlers
application.add_handler(conv_handler)
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("ping", ping_command))
application.add_handler(CommandHandler("status", status_command))
application.add_handler(CommandHandler("cancel", cancel_command))
application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

# ====== Flask Web Server & Async init/start ======
app = Flask(__name__)

def start_bot_loop():
    # Create new event loop for this thread and run app lifecycle
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()

    loop.run_until_complete(application.initialize())
    loop.run_until_complete(application.start())

    logger.info("Bot started and initialized")
    loop.run_forever()

# Start the bot event loop in separate thread so Flask can run normally
threading.Thread(target=start_bot_loop, daemon=True).start()

@app.route("/", methods=["GET"])
def index():
    return "Bot1 Lapor Belanja is running."

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    loop = asyncio.get_event_loop()

    # Dispatch update processing to the bot loop
    asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    return "OK"

if __name__ == "__main__":
    # Flask default port 5000, but Render typically overrides with PORT env
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
