import os
import io
import base64
import datetime
import logging
from flask import Flask, request
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from PIL import Image
import pytesseract  # pastikan pytesseract dan Tesseract OCR installed di server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT1_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

# States untuk ConversationHandler
(ASK_LOCATION, ASK_MORE_ITEMS, ASK_UPLOAD_IMAGE) = range(3)

# Simpan sementara data user sebelum save ke Sheets
user_data_cache = {}

# Setup Google Sheets API
def get_gsheet_service():
    creds_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
    creds = Credentials.from_service_account_info(eval(creds_json.decode("utf-8")),
                                                  scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build('sheets', 'v4', credentials=creds)
    return service

def append_row_to_sheet(row):
    service = get_gsheet_service()
    sheet = service.spreadsheets()
    sheet.values().append(
        spreadsheetId=SHEET_ID,
        range="Sheet1!A:G",
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()

# Simpan gambar ke folder 'receipt_images' di lokal
def save_receipt_image(file_bytes, chat_id):
    folder = "receipt_images"
    os.makedirs(folder, exist_ok=True)
    filename = f"{folder}/{chat_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    with open(filename, "wb") as f:
        f.write(file_bytes)
    return filename

# Ekstrak data kasar dari gambar OCR
def extract_receipt_data(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image, lang='eng')
    logger.info(f"OCR Text: {text}")

    # Contoh simple parse - anda boleh tambah parse yang lebih advance
    # Cari tarikh (YYYY-MM-DD / DD/MM/YYYY), jumlah, kedai, dan item ringkas
    import re
    date_pattern = r'(\d{4}[-/]\d{2}[-/]\d{2})|(\d{2}[/]\d{2}[/]\d{4})'
    amount_pattern = r'Total\s*:?\s*RM?(\d+\.\d{2})'
    shop_pattern = r'(?:Shop|Store|Kedai|Merchant)\s*:\s*(.*)'

    tarikh = re.search(date_pattern, text)
    jumlah = re.search(amount_pattern, text, re.IGNORECASE)
    kedai = re.search(shop_pattern, text, re.IGNORECASE)

    tarikh_str = tarikh.group(0) if tarikh else datetime.date.today().strftime("%Y-%m-%d")
    jumlah_str = jumlah.group(1) if jumlah else "0.00"
    kedai_str = kedai.group(1).strip() if kedai else "Unknown"

    # Items (just demo, ambil baris yg ada harga)
    items = []
    for line in text.split('\n'):
        if re.search(r'\d+\.\d{2}', line):
            items.append(line.strip())
    jumlah_items = len(items)

    return tarikh_str, kedai_str, items, jumlah_items, jumlah_str

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selamat datang ke LaporBelanjaBot!\n"
        "Hantar resit gambar atau taip maklumat belanja anda.\n"
        "Contoh: nasi ayam rm10.50\n"
        "Bot akan bantu anda simpan rekod."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.lower()

    # Cuba detect ringkas jumlah dan barang
    import re
    amt = re.findall(r'(\d+\.\d{2})', text)
    if amt:
        jumlah = amt[-1]
    else:
        jumlah = None

    # Simpan data sementara
    user_data_cache[chat_id] = {
        "tarikh": datetime.date.today().strftime("%Y-%m-%d"),
        "masa": datetime.datetime.now().strftime("%H:%M:%S"),
        "lokasi": None,
        "items": [text],
        "jumlah_items": 1,
        "jumlah_belanja": jumlah,
        "chat_id": chat_id
    }

    if user_data_cache[chat_id]["lokasi"] is None:
        await update.message.reply_text("Di mana lokasi/kedai belanja ini?")
        return ASK_LOCATION
    else:
        await update.message.reply_text("Ada lagi barang lain?")
        return ASK_MORE_ITEMS

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lokasi = update.message.text
    if chat_id in user_data_cache:
        user_data_cache[chat_id]["lokasi"] = lokasi
    await update.message.reply_text("Ada lagi barang lain? Kalau sudah, hantar gambar resit atau taip 'tidak'.")
    return ASK_MORE_ITEMS

async def ask_more_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.lower()

    if text in ['tidak', 'tak', 'no']:
        await update.message.reply_text("Sila upload gambar resit untuk simpan rekod, atau taip 'skip' untuk terus simpan data.")
        return ASK_UPLOAD_IMAGE
    else:
        if chat_id in user_data_cache:
            user_data_cache[chat_id]["items"].append(text)
            user_data_cache[chat_id]["jumlah_items"] += 1
        await update.message.reply_text("Ada lagi barang lain? Kalau sudah, hantar gambar resit atau taip 'tidak'.")
        return ASK_MORE_ITEMS

async def ask_upload_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.lower()
    if text == "skip":
        # Simpan data tanpa gambar
        data = user_data_cache.get(chat_id)
        if data:
            row = [
                data["tarikh"],
                data["masa"],
                data["lokasi"],
                "\n".join(data["items"]),
                data["jumlah_items"],
                data["jumlah_belanja"] or "0.00",
                str(chat_id)
            ]
            append_row_to_sheet(row)
            await update.message.reply_text("Data belanja anda telah disimpan. Terima kasih!")
            user_data_cache.pop(chat_id, None)
        else:
            await update.message.reply_text("Tiada data untuk disimpan.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Sila hantar gambar resit sekarang.")
        return ASK_UPLOAD_IMAGE

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    tarikh, kedai, items, jumlah_items, jumlah_belanja = extract_receipt_data(photo_bytes)
    filename = save_receipt_image(photo_bytes, chat_id)

    # Simpan ke Google Sheets
    row = [
        tarikh,
        datetime.datetime.now().strftime("%H:%M:%S"),
        kedai,
        "\n".join(items),
        jumlah_items,
        jumlah_belanja,
        str(chat_id)
    ]
    append_row_to_sheet(row)

    await update.message.reply_text(
        f"Resit telah diproses dan disimpan.\n"
        f"Tarikh: {tarikh}\n"
        f"Kedai: {kedai}\n"
        f"Jumlah items: {jumlah_items}\n"
        f"Jumlah belanja: RM{jumlah_belanja}\n"
        f"Fail gambar disimpan: {filename}"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_cache.pop(update.effective_chat.id, None)
    await update.message.reply_text("Transaksi dibatalkan.")
    return ConversationHandler.END

application = Application.builder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text), MessageHandler(filters.PHOTO, handle_photo)],
    states={
        ASK_LOCATION: [MessageHandler(filters.TEXT & (~filters.COMMAND), ask_location)],
        ASK_MORE_ITEMS: [MessageHandler(filters.TEXT & (~filters.COMMAND), ask_more_items), MessageHandler(filters.PHOTO, handle_photo)],
        ASK_UPLOAD_IMAGE: [MessageHandler(filters.PHOTO, handle_photo), MessageHandler(filters.TEXT & (~filters.COMMAND), ask_upload_image)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

application.add_handler(CommandHandler("start", start))
application.add_handler(conv_handler)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
