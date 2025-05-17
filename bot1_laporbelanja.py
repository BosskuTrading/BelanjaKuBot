import os
import logging
import asyncio
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import base64
import json
import re

# ====== Setup logging ======
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====== Environment variables ======
BOT_TOKEN = os.getenv("BOT1_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

if not all([BOT_TOKEN, SPREADSHEET_ID, GOOGLE_CREDENTIALS_BASE64]):
    logger.error("Sila set semua environment variables: BOT1_TOKEN, SPREADSHEET_ID, GOOGLE_CREDENTIALS_BASE64")
    exit(1)

# ====== Google Sheets setup ======
try:
    credentials_dict = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_BASE64))
    credentials = Credentials.from_service_account_info(credentials_dict)
    sheet_service = build('sheets', 'v4', credentials=credentials)
    sheet = sheet_service.spreadsheets()
except Exception as e:
    logger.error(f"Gagal setup Google Sheets API: {e}")
    exit(1)

def append_to_sheet(row):
    try:
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Sheet1!A:F",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        logger.info(f"Berjaya tambah baris: {row}")
    except Exception as e:
        logger.error(f"Ralat tambah data ke Sheet: {e}")

# ====== OCR / Parsing Dummy ======
def perform_ocr(image_bytes):
    # Dummy OCR - ganti dengan integrasi Google Vision API atau lain
    return "12/05/2025 MyKedai RM23.50"

def parse_date(text):
    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    return m.group(1) if m else None

def parse_amount(text):
    m = re.search(r"RM?(\d+[\.,]?\d*)", text, re.IGNORECASE)
    if m:
        return m.group(1).replace(",", ".")
    return None

# ====== Telegram bot setup ======

app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()

CHOICES = [["Taip Belanja", "Hantar Resit"]]

# ---- Command Handlers ----
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "Cara guna bot ini:\n"
        "1. Pilih 'Taip Belanja' untuk masukkan maklumat belanja secara manual.\n"
        "2. Pilih 'Hantar Resit' untuk hantar gambar resit pembelian.\n"
        "3. Saya akan rekod maklumat anda ke Google Sheets.\n"
        "4. Gunakan /status untuk semak berapa banyak resit yang anda dah hantar.\n"
        "5. Gunakan /ping untuk semak sama ada bot ini sedang aktif.\n"
        "6. Gunakan /cancel untuk batal mod taip manual.\n\n"
        "Kalau ada sebarang masalah, sila hubungi admin ya."
    )
    await update.message.reply_text(help_msg, reply_markup=ReplyKeyboardRemove())

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot sedang online dan sedia membantu anda! ✅")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Sheet1!A:A").execute()
        values = result.get("values", [])
        count = sum(1 for row in values if row and row[0] == str(chat_id))
        await update.message.reply_text(
            f"Anda telah menghantar {count} resit atau belanja ke bot ini. Terima kasih! 👍"
        )
    except Exception as e:
        logger.error(f"Ralat semak status: {e}")
        await update.message.reply_text(
            "Maaf, saya tidak dapat semak status anda sekarang."
        )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["expecting_manual_input"] = False
    await update.message.reply_text(
        "Mode taip manual dibatalkan. Sila pilih /start untuk mula semula.",
        reply_markup=ReplyKeyboardRemove()
    )

# ---- Message Handlers ----
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "taip belanja" in text:
        await update.message.reply_text(
            "Sila taip maklumat belanja anda dalam format mudah seperti:\n\n"
            "Tarikh(dd/mm/yyyy) NamaKedai Jumlah\n\n"
            "Contoh:\n12/05/2025 MyKedai 23.50",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["expecting_manual_input"] = True
    elif "hantar resit" in text:
        await update.message.reply_text(
            "Baik! Sila hantar gambar resit pembelian anda sekarang.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["expecting_manual_input"] = False
    else:
        await update.message.reply_text(
            "Maaf, saya tidak faham pilihan anda. Sila pilih 'Taip Belanja' atau 'Hantar Resit'.",
            reply_markup=ReplyKeyboardMarkup(CHOICES, one_time_keyboard=True, resize_keyboard=True)
        )

async def handle_manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("expecting_manual_input"):
        text = update.message.text.strip()
        parts = text.split()
        if len(parts) < 3:
            await update.message.reply_text(
                "Format tidak betul. Sila taip semula dengan format:\n"
                "Tarikh(dd/mm/yyyy) NamaKedai Jumlah\nContoh: 12/05/2025 MyKedai 23.50"
            )
            return

        tarikh, jumlah = parts[0], parts[-1]
        nama_kedai = " ".join(parts[1:-1])

        try:
            datetime.strptime(tarikh, "%d/%m/%Y")
        except ValueError:
            await update.message.reply_text(
                "Tarikh tidak sah. Sila guna format dd/mm/yyyy, contoh: 12/05/2025"
            )
            return

        try:
            jumlah_val = float(jumlah)
        except ValueError:
            await update.message.reply_text(
                "Jumlah tidak sah. Sila taip nombor seperti 23.50"
            )
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(update.effective_chat.id), now_str, tarikh, nama_kedai, f"{jumlah_val:.2f}", "Manual Input"]
        append_to_sheet(row)

        await update.message.reply_text(
            "✅ Maklumat belanja anda telah direkodkan!\n"
            f"🗓 Tarikh: {tarikh}\n"
            f"🏪 Kedai: {nama_kedai}\n"
            f"💰 Jumlah: RM {jumlah_val:.2f}\n\n"
            "Terima kasih kerana menggunakan bot ini.\n"
            "Taip /status untuk semak jumlah belanja anda."
        )
        context.user_data["expecting_manual_input"] = False
    else:
        await update.message.reply_text(
            "Maaf, saya tidak faham. Sila pilih /help untuk panduan atau gunakan pilihan yang disediakan."
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("expecting_manual_input"):
        await update.message.reply_text(
            "Anda dalam mod taip belanja. Sila taip maklumat belanja atau taip /cancel untuk batal mod."
        )
        return

    photos = update.message.photo
    if not photos:
        await update.message.reply_text(
            "Maaf, gambar tidak ditemui. Sila cuba hantar semula."
        )
        return

    photo_file = photos[-1]
    file = await context.bot.get_file(photo_file.file_id)
    image_bytes = await file.download_as_bytearray()
    image_bytes = bytes(image_bytes)  # pastikan type bytes untuk OCR

    text_detected = perform_ocr(image_bytes)
    if not text_detected.strip():
        await update.message.reply_text(
            "Maaf, saya tidak dapat membaca resit. Sila cuba gambar yang lebih jelas."
        )
        return

    tarikh = parse_date(text_detected)
    jumlah = parse_amount(text_detected)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = [str(update.effective_chat.id), now_str, tarikh or "-", jumlah or "-", "OCR Input"]
    append_to_sheet(row)

    reply_msg = (
        "✅ Resit anda telah direkodkan!\n"
        f"🗓 Tarikh (jika dapat dikesan): {tarikh or '-'}\n"
        f"💰 Jumlah (jika dapat dikesan): {jumlah or '-'}\n\n"
        "Terima kasih kerana menggunakan bot ini.\n"
        "Taip /status untuk semak jumlah resit anda."
    )
    await update.message.reply_text(reply_msg)

async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Maaf, saya tidak faham mesej itu.\n"
        "Sila gunakan pilihan yang disediakan atau taip /help untuk panduan."
    )

# ---- Register handlers ----
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("status", status_command))
application.add_handler(CommandHandler("ping", ping_command))
application.add_handler(CommandHandler("cancel", cancel_command))

application.add_handler(MessageHandler(filters.Regex("^(Taip Belanja|Hantar Resit)$"), handle_choice))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_manual_input))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(MessageHandler(filters.COMMAND, unknown_text))

# ====== Flask webhook setup ======
@app.route("/", methods=["GET"])
def index():
    return "Bot1 Lapor Belanja is running."

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "OK"

# ====== Run Flask app ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
