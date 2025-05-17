import os
import base64
import json
import logging
from flask import Flask, request
from google.cloud import vision
from google.oauth2 import service_account
import gspread
from telegram import Bot
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

BOT1_TOKEN = os.getenv("BOT1_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

if not all([BOT1_TOKEN, SPREADSHEET_ID, GOOGLE_CREDENTIALS_BASE64]):
    raise Exception("Missing environment variables: BOT1_TOKEN, SPREADSHEET_ID, or GOOGLE_CREDENTIALS_BASE64")

google_creds_bytes = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
creds_dict = json.loads(google_creds_bytes.decode("utf-8"))
creds = service_account.Credentials.from_service_account_info(creds_dict)
scoped_creds = creds.with_scopes([
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])

gc = gspread.authorize(scoped_creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
vision_client = vision.ImageAnnotatorClient(credentials=scoped_creds)
bot = Bot(token=BOT1_TOKEN)
app = Flask(__name__)

def extract_text_from_image(image_bytes):
    image = vision.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

def parse_receipt(text):
    lines = text.strip().split("\n")
    total = ""
    for line in reversed(lines):
        if "total" in line.lower():
            total = line
            break
    return {
        "raw": text.replace("\n", " | "),
        "total_line": total
    }

@app.route(f"/{BOT1_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    logger.info(f"Update received: {update}")

    if "message" not in update:
        return "ok"

    message = update["message"]
    chat_id = message["chat"]["id"]

    try:
        if "text" in message:
            text = message["text"]
            if text == "/start":
                bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "👋 Selamat datang ke *LaporBelanjaBot*!\n\n"
                        "Hantar gambar resit belanja anda kepada saya, dan saya akan tolong simpan dan rekodkan data secara automatik.\n\n"
                        "📸 Pastikan gambar jelas dan lengkap ya.\n"
                        "Jika ada masalah, taip /help untuk bantuan."
                    ),
                    parse_mode="Markdown"
                )
                return "ok"

            elif text == "/help":
                bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "Cara guna *LaporBelanjaBot*:\n"
                        "1. Hantar gambar resit belanja anda.\n"
                        "2. Saya akan baca dan simpan maklumat belanja secara automatik.\n"
                        "3. Anda boleh semak laporan melalui bot laporan.\n\n"
                        "Jika ada sebarang masalah, hubungi pembangun."
                    ),
                    parse_mode="Markdown"
                )
                return "ok"

            else:
                bot.send_message(
                    chat_id=chat_id,
                    text="🤖 Saya tak faham mesej ini. Sila hantar gambar resit atau taip /help untuk arahan."
                )
                return "ok"

        elif "photo" in message:
            bot.send_message(chat_id=chat_id, text="📸 Terima kasih, saya sedang proses gambar resit anda...")

            file_id = message["photo"][-1]["file_id"]
            file = bot.get_file(file_id)
            file_bytes = file.download_as_bytearray()

            extracted_text = extract_text_from_image(file_bytes)
            if not extracted_text.strip():
                bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "⚠️ Maaf, saya tidak dapat membaca teks dari gambar resit anda.\n"
                        "Sila cuba ambil gambar dengan lebih jelas dan lengkap."
                    )
                )
                return "ok"

            parsed = parse_receipt(extracted_text)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sheet.append_row([
                str(chat_id),
                now,
                parsed["raw"],
                parsed["total_line"]
            ])

            bot.send_message(
                chat_id=chat_id,
                text=(
                    "✅ Resit berjaya diproses dan disimpan!\n\n"
                    "Maklumat yang saya dapat:\n"
                    f"{parsed['total_line'] or '(Jumlah tidak dapat dikenalpasti)'}\n\n"
                    "Teruskan hantar resit jika ada lebih banyak."
                )
            )
            return "ok"

        else:
            bot.send_message(
                chat_id=chat_id,
                text="🤖 Sila hantar gambar resit supaya saya boleh bantu rekod belanja anda."
            )
            return "ok"

    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        bot.send_message(
            chat_id=chat_id,
            text="⚠️ Maaf, berlaku masalah semasa memproses permintaan anda. Sila cuba lagi nanti."
        )
        return "ok"

@app.route("/", methods=["GET"])
def index():
    return "Bot1 LaporBelanja is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
