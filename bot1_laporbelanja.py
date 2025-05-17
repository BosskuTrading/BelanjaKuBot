import os
import logging
from datetime import datetime
from flask import Flask, request, abort
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

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger("bot1_laporbelanja")

# Google Sheets Setup
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

# Dummy OCR (Replace with real OCR implementation)
def perform_ocr(image_bytes):
    return "12/05/2025 MyKedai RM23.50"

def parse_date(text):
    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    return m.group(1) if m else None

def parse_amount(text):
    m = re.search(r"RM?(\d+[\.,]?\d*)", text, re.IGNORECASE)
    if m:
        return m.group(1).replace(",", ".")
    return None

def parse_flexible_input(text):
    text = text.strip()
    date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    tarikh = None
    if date_match:
        tarikh_str = date_match.group(1)
        try:
            datetime.strptime(tarikh_str, "%d/%m/%Y")
            tarikh = tarikh_str
        except ValueError:
            tarikh = None
        text = text.replace(tarikh_str, "").strip()
    amounts = re.findall(r"\d+(?:[\.,]\d+)?", text)
    jumlah = None
    if amounts:
        jumlah_str = amounts[-1].replace(",", ".")
        try:
            jumlah = float(jumlah_str)
        except ValueError:
            jumlah = None
        text = text.replace(amounts[-1], "").strip()
    if jumlah is None:
        return None
    nama_menu = text.strip()
    if not nama_menu:
        return None
    if tarikh is None:
        tarikh = datetime.now().strftime("%d/%m/%Y")
    return tarikh, nama_menu, jumlah

BOT_TOKEN = os.getenv("BOT1_TOKEN")

app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()

CHOICES = [["Taip Belanja", "Hantar Resit"]]

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
        "Kalau ada masalah, sila hubungi admin."
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

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if context.user_data.get("expecting_manual_input"):
        parsed = parse_flexible_input(update.message.text)
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

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    ocr_text = perform_ocr(photo_bytes)
    tarikh = parse_date(ocr_text) or datetime.now().strftime("%d/%m/%Y")
    jumlah_str = parse_amount(ocr_text)
    try:
        jumlah = float(jumlah_str) if jumlah_str else None
    except Exception:
        jumlah = None

    if not jumlah:
        await update.message.reply_text(
            "Maaf, saya tidak dapat kenal pasti jumlah dalam resit anda. "
            "Sila cuba taip belanja secara manual."
        )
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nama_menu = "Resit Gambar"
    row = [str(update.effective_chat.id), now_str, tarikh, nama_menu, f"{jumlah:.2f}", "Gambar Resit"]
    append_to_sheet(row)

    await update.message.reply_text(
        f"✅ Resit anda telah berjaya direkodkan!\n"
        f"🗓 Tarikh: {tarikh}\n"
        f"💰 Jumlah: RM {jumlah:.2f}\n\n"
        "Terima kasih kerana menggunakan bot ini.\n"
        "Taip /status untuk semak jumlah belanja anda."
    )

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("ping", ping_command))
application.add_handler(CommandHandler("status", status_command))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

# Flask webhook route with token validation
@app.route("/webhook/<token>", methods=["POST"])
async def webhook(token):
    if token != BOT_TOKEN:
        abort(403)
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, application.bot)
    await application.update_queue.put(update)
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
