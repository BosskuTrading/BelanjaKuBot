import os
import telebot
import pytesseract
import tempfile
import datetime
import io
from flask import Flask, request
from PIL import Image
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import base64
import json

# Telegram Bot Token
BOT_TOKEN = os.environ.get("BOT1_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Google Sheets
SPREADSHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")

# Decode credentials
creds_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode("utf-8")
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict)
sheets_service = build('sheets', 'v4', credentials=creds)

# Flask app
app = Flask(__name__)

# Welcome message
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "📸 Selamat datang ke *Lapor Belanja Bot*! Hantar gambar resit atau taip belanja (cth: `RM12.50 Nasi Ayam @ Restoran ABC`)", parse_mode="Markdown")

# Terima teks manual
@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = message.text
    save_to_sheet([str(chat_id), now, "TEKS", text, "-", "-", "-"])
    bot.reply_to(message, "✅ Maklumat telah direkod.")

# Terima gambar
@bot.message_handler(content_types=['photo'])
def handle_image(message):
    chat_id = message.chat.id
    photo = message.photo[-1]
    file_info = bot.get_file(photo.file_id)
    downloaded = bot.download_file(file_info.file_path)

    # Simpan gambar sementara
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
        temp.write(downloaded)
        temp_path = temp.name

    # OCR
    text = pytesseract.image_to_string(Image.open(temp_path))

    # Proses ringkas (boleh ditambah baik)
    extracted = extract_data_from_text(text)

    # Simpan ke Google Sheets
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_to_sheet([str(chat_id), now] + extracted)

    bot.reply_to(message, f"✅ Resit diproses dan data direkod:\n\n{format_data(extracted)}")

def extract_data_from_text(text):
    lines = text.splitlines()
    text = '\n'.join(lines)
    # Dummy extractor
    tarikh = cari_tarikh(text)
    nama_kedai = lines[0] if lines else "?"
    jumlah = cari_jumlah(text)
    return [tarikh, nama_kedai, "-", "-", jumlah]

def cari_tarikh(text):
    import re
    match = re.search(r'(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{2,4})', text)
    return match.group(1) if match else "-"

def cari_jumlah(text):
    import re
    match = re.findall(r'RM?\s?(\d+\.\d{2})', text, re.IGNORECASE)
    return match[-1] if match else "-"

def format_data(data):
    return f"📅 Tarikh: {data[0]}\n🏪 Kedai: {data[1]}\n💵 Jumlah: {data[-1]}"

def save_to_sheet(row):
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="Sheet1!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()

# Flask route
@app.route('/', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/', methods=['GET'])
def index():
    return "Bot is running", 200

# Set webhook manually (once)
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=os.environ.get("WEBHOOK_URL"))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
