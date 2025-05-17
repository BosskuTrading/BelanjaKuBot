import os
import logging
import base64
import io
from flask import Flask, request
from telegram import Bot
from telegram.constants import ParseMode
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import vision
from PIL import Image

# Logging
logging.basicConfig(level=logging.INFO)

# Flask app
app = Flask(__name__)

# Env vars
BOT1_TOKEN = os.environ.get("BOT1_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")

if not BOT1_TOKEN or not SPREADSHEET_ID or not GOOGLE_CREDENTIALS_BASE64:
    raise Exception("Missing environment variables: BOT1_TOKEN, SPREADSHEET_ID, or GOOGLE_CREDENTIALS_BASE64")

bot = Bot(token=BOT1_TOKEN)

# Google credentials
creds_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode("utf-8")
creds = service_account.Credentials.from_service_account_info(eval(creds_json))
sheets_service = build("sheets", "v4", credentials=creds)
sheet = sheets_service.spreadsheets()

# Google Vision
vision_client = vision.ImageAnnotatorClient(credentials=creds)

# Welcome
@app.route(f"/{BOT1_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        logging.info(f"Update: {update}")

        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]

            if "text" in message:
                text = message["text"]

                if text.startswith("/start"):
                    bot.send_message(
                        chat_id=chat_id,
                        text="👋 Hai! Saya adalah bot pencatat belanja anda.\n\n📸 Sila hantar gambar resit atau taip jumlah & butiran belanja (cth: `RM12.50 Makan tengahari`) untuk direkodkan.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    # Simpan teks ke Google Sheets
                    values = [[
                        message["date"],
                        message["from"]["id"],
                        message["from"].get("username", ""),
                        text
                    ]]
                    sheet.values().append(
                        spreadsheetId=SPREADSHEET_ID,
                        range="Data!A:D",
                        valueInputOption="USER_ENTERED",
                        body={"values": values}
                    ).execute()

                    bot.send_message(
                        chat_id=chat_id,
                        text="✅ Terima kasih! Catatan belanja anda telah disimpan.\n\n📊 Anda boleh lihat laporan mingguan/bulanan melalui bot laporan nanti.",
                    )

            elif "photo" in message:
                file_id = message["photo"][-1]["file_id"]
                file = bot.get_file(file_id)
                file_bytes = io.BytesIO()
                file.download(out=file_bytes)
                file_bytes.seek(0)

                image = vision.Image(content=file_bytes.read())
                response = vision_client.text_detection(image=image)
                texts = response.text_annotations

                if not texts:
                    bot.send_message(chat_id=chat_id, text="⚠️ Maaf, tiada teks dapat dibaca dari gambar. Cuba semula dengan gambar yang lebih jelas.")
                    return "OK"

                raw_text = texts[0].description

                # Simpan ke Google Sheets
                values = [[
                    message["date"],
                    message["from"]["id"],
                    message["from"].get("username", ""),
                    raw_text
                ]]
                sheet.values().append(
                    spreadsheetId=SPREADSHEET_ID,
                    range="Data!A:D",
                    valueInputOption="USER_ENTERED",
                    body={"values": values}
                ).execute()

                bot.send_message(
                    chat_id=chat_id,
                    text="🧾 Resit anda telah diterima dan diproses!\n\n✅ Data telah disimpan ke rekod belanja anda."
                )

            else:
                bot.send_message(chat_id=chat_id, text="ℹ️ Sila hantar teks belanja atau gambar resit untuk diproses.")

    except Exception as e:
        logging.exception("Error handling webhook:")
        if "chat_id" in locals():
            bot.send_message(chat_id=chat_id, text="❌ Maaf, berlaku ralat semasa memproses mesej anda.")
    return "OK"

# Health check
@app.route("/")
def index():
    return "Bot LaporBelanja Aktif!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
