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
)
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import base64
import json
import re

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger("bot1_laporbelanja")

# ====== Google Sheets Setup ======
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

credentials_dict = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_BASE64))
credentials = Credentials.from_service_account_info(credentials_dict)
sheet_service = build('sheets', 'v4', credentials=credentials)
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
    # Example OCR output: "12/05/2025 MyKedai RM23.50"
    return "12/05/2025 MyKedai RM23.50"

def parse_date(text):
    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    return m.group(1) if m else None

def parse_amount(text):
    m = re.search(r"RM?(\d+[\.,]?\d*)", text, re.IGNORECASE)
    if m:
        return m.group(1).replace(",", ".")
    return None

# ====== Flexible manual input parser ======
def parse_flexible_input(text):
    text = text.strip()

    # 1. Cari tarikh (dd/mm/yyyy)
    date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    tarikh = None
    if date_match:
        tarikh_str = date_match.group(1)
        try:
            datetime.strptime(tarikh_str, "%d/%m/%Y")
            tarikh = tarikh_str
        except ValueError:
            tarikh = None
        # keluarkan tarikh dari text
        text = text.replace(tarikh_str, "").strip()

    # 2. Cari semua nombor decimal
    amounts = re.findall(r"\d+(?:[\.,]\d+)?", text)
    jumlah = None
    if amounts:
        jumlah_str = amounts[-1].replace(",", ".")
        try:
            jumlah = float(jumlah_str)
        except ValueError:
            jumlah = None
        # keluarkan jumlah dari text
        text = text.replace(amounts[-1], "").strip()

    if jumlah is None:
        return None  # tak jumpa jumlah valid

    # 3. Apa yang tinggal dianggap nama kedai + menu
    nama_menu = text.strip()
    if not nama_menu:
        return None

    # Kalau tarikh tiada, guna tarikh hari ini
    if tarikh is None:
        tarikh = datetime.now().strftime("%d/%m/%Y")

    return tarikh, nama_menu, jumlah

# ====== Telegram Bot Setup ======
BOT_TOKEN = os.getenv("BOT1_TOKEN")

app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()

CHOICES = [["Taip Belanja", "Hantar Resit"]]

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or "Sahabat"
    welcome_msg = (
        f"Hai {user_first_name}! 👋\n\n"
        "Saya adalah pembantu belanja anda.\n"
        "Bot ini dibawakan oleh Fadirul Ezwan.\n\n"
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
        "5. Gunakan /ping untuk semak sama ada bot ini sedang aktif.\n\n"
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

# --- Message Handlers ---
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "taip belanja" in text:
        await update.message.reply_text(
            "Sila taip maklumat belanja anda mengandungi:\n\n"
            "- Tarikh (optional) dalam format dd/mm/yyyy\n"
            "- Nama kedai dan menu\n"
            "- Jumlah (wajib ada)\n\n"
            "Boleh taip dalam apa-apa susunan.\n\n"
            "Contoh:\n"
            "MyKedai Nasi Lemak 12/05/2025 23.50\n"
            "23.50 Nasi Lemak MyKedai\n"
            "Nasi Lemak 23.50\n"
            "12/05/2025 23.50 MyKedai Nasi Lemak",
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
        parsed = parse_flexible_input(text)
        if not parsed:
            await update.message.reply_text(
                "Format tidak betul.\n"
                "Sila taip maklumat belanja anda yang mengandungi:\n"
                "- Tarikh (optional) dalam format dd/mm/yyyy\n"
                "- Nama kedai dan menu (boleh di mana-mana sahaja)\n"
                "- Jumlah (wajib ada)\n\n"
                "Contoh:\n"
                "MyKedai Nasi Lemak 12/05/2025 23.50\n"
                "23.50 Nasi Lemak MyKedai\n"
                "Nasi Lemak 23.50\n"
                "12/05/2025 23.50 MyKedai Nasi Lemak"
            )
            return

        tarikh, nama_menu, jumlah = parsed
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [str(update.effective_chat.id), now_str, tarikh, nama_menu, f"{jumlah:.2f}", "Manual Input"]
        append_to_sheet(row)

        await update.message.reply_text(
            "✅ Maklumat belanja anda telah direkodkan!\n"
            f"🗓 Tarikh: {tarikh}\n"
            f"🏪 Kedai + Menu: {nama_menu}\n"
            f"💰 Jumlah: RM {jumlah:.2f}\n\n"
            "Terima kasih kerana menggunakan bot ini.\n"
            "Taip /status untuk semak jumlah belanja anda."
        )
        context.user_data["expecting_manual_input"] = False
    else:
        await update.message.reply_text(
            "Maaf, saya tidak faham. Sila pilih /help untuk panduan atau gunakan pilihan yang disediakan."
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    # Placeholder: Gantikan dengan panggilan sebenar OCR
    ocr_text = perform_ocr(photo_bytes)

    # Cuba parse hasil OCR (example dummy parse)
    tarikh = parse_date(ocr_text) or datetime.now().strftime("%d/%m/%Y")
    jumlah_str = parse_amount(ocr_text)
    if jumlah_str:
        try:
            jumlah = float(jumlah_str)
        except ValueError:
            jumlah = None
    else:
        jumlah = None

    nama_menu = ocr_text
    if tarikh:
        nama_menu = nama_menu.replace(tarikh, "").strip()
    if jumlah_str:
        nama_menu = nama_menu.replace(jumlah_str, "").strip()
    if not nama_menu:
        nama_menu = "Unknown"

    if jumlah is None:
        await update.message.reply_text(
            "Maaf, saya tidak dapat kenal pasti jumlah belanja dari resit tersebut.\n"
            "Sila taip maklumat belanja secara manual."
        )
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [str(update.effective_chat.id), now_str, tarikh, nama_menu, f"{jumlah:.2f}", "Photo OCR"]
    append_to_sheet(row)

    await update.message.reply_text(
        "✅ Resit anda telah direkodkan!\n"
        f"🗓 Tarikh: {tarikh}\n"
        f"🏪 Kedai + Menu: {nama_menu}\n"
        f"💰 Jumlah: RM {jumlah:.2f}\n\n"
        "Terima kasih kerana menggunakan bot ini.\n"
        "Taip /status untuk semak jumlah belanja anda."
    )

# --- Main Dispatcher Registration ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("ping", ping_command))
application.add_handler(CommandHandler("status", status_command))

application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_choice))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_manual_input))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

# ====== Flask Webhook Setup ======

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.update_queue.put(update))
    return "OK"

if __name__ == "__main__":
    # Use threaded=True to allow Telegram processing alongside Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=True)
