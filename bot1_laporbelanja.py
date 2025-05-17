import os
import logging
import json
import datetime
import io
import asyncio
from flask import Flask, request, abort
from telegram import Update, Bot, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import pytesseract
from PIL import Image

# --- CONFIG ---
TOKEN_BOT1 = os.getenv("TOKEN_BOT1")
SHEET_ID = os.getenv("SHEET_ID")
DATA_FOLDER = "data_resit"

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# Load Google Credentials JSON from env
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not GOOGLE_CREDENTIALS_JSON:
    raise RuntimeError("Missing Google Credentials in GOOGLE_CREDENTIALS_JSON env var")

credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
credentials = Credentials.from_service_account_info(credentials_info)
sheets_service = build('sheets', 'v4', credentials=credentials)

bot = Bot(token=TOKEN_BOT1)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- TELEGRAM APPLICATION ---
application = ApplicationBuilder().token(TOKEN_BOT1).build()

# --- HELPERS ---

def save_image_file(photo_file, chat_id, timestamp):
    filename = f"{chat_id}_{timestamp}.jpg"
    filepath = os.path.join(DATA_FOLDER, filename)
    photo_file.download(filepath)
    return filepath

def ocr_extract_text(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return ""

def parse_expense_text(text):
    lines = text.splitlines()
    date_str = ""
    time_str = ""
    shop = ""
    items = []
    total_amount = 0.0
    total_items = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not date_str:
            try:
                date_obj = datetime.datetime.strptime(line, "%Y-%m-%d")
                date_str = date_obj.strftime("%Y-%m-%d")
                continue
            except:
                pass
            try:
                date_obj = datetime.datetime.strptime(line, "%d/%m/%Y")
                date_str = date_obj.strftime("%Y-%m-%d")
                continue
            except:
                pass
        if not time_str:
            if ":" in line and len(line) <= 5:
                time_str = line
                continue
        if not shop and any(c.isalpha() for c in line):
            shop = line
            continue
        if "rm" in line.lower():
            parts = line.lower().split("rm")
            try:
                amount = float(parts[-1].strip())
                total_amount += amount
                items.append(line)
                total_items += 1
            except:
                pass

    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if not time_str:
        time_str = datetime.datetime.now().strftime("%H:%M:%S")

    return date_str, time_str, shop, items, total_items, total_amount

def append_to_sheet(row_data):
    try:
        sheet = sheets_service.spreadsheets()
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": [row_data]},
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Failed append to sheet: {e}")
        return False

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Salam {user.first_name}! 👋\n"
        "Hantar gambar resit atau teks belanja anda.\n"
        "Saya akan simpan dan rekodkan untuk laporan.\n"
        "Gunakan /help untuk bantuan."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cara guna bot ini:\n"
        "- Hantar gambar resit.\n"
        "- Atau hantar teks belanja seperti:\n"
        "  Tarikh, Masa, Kedai, Senarai item; Jumlah item; Jumlah harga\n"
        "Contoh:\n2025-05-17, 10:30, Kedai ABC, Nasi Lemak 2 RM6.00; 2; 6.00"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    timestamp = int(datetime.datetime.now().timestamp())
    photos = update.message.photo
    if not photos:
        await update.message.reply_text("Tiada gambar dikesan.")
        return
    largest_photo = photos[-1]
    photo_file = await context.bot.get_file(largest_photo.file_id)

    filepath = save_image_file(photo_file, chat_id, timestamp)
    logger.info(f"Saved photo to {filepath}")

    text = ocr_extract_text(filepath)
    logger.info(f"OCR text: {text}")

    date_str, time_str, shop, items, total_items, total_amount = parse_expense_text(text)

    row = [
        date_str,
        time_str,
        shop,
        "\n".join(items),
        str(total_items),
        f"{total_amount:.2f}",
        str(chat_id),
    ]

    if append_to_sheet(row):
        await update.message.reply_text(
            f"Resit diterima dan direkodkan.\nTarikh: {date_str}\nKedai: {shop}\nJumlah: RM{total_amount:.2f}"
        )
    else:
        await update.message.reply_text("Gagal simpan data ke Google Sheets.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    try:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 4:
            raise ValueError("Format salah")
        date_str = parts[0]
        time_str = parts[1]
        shop = parts[2]
        rest = ",".join(parts[3:])
        if ";" in rest:
            items_part, total_items_str, total_amount_str = [x.strip() for x in rest.split(";")]
        else:
            items_part = rest
            total_items_str = "0"
            total_amount_str = "0"

        row = [
            date_str,
            time_str,
            shop,
            items_part,
            total_items_str,
            total_amount_str,
            str(chat_id),
        ]
        if append_to_sheet(row):
            await update.message.reply_text("Data belanja diterima dan direkodkan.")
        else:
            await update.message.reply_text("Gagal simpan data ke Google Sheets.")
    except Exception as e:
        logger.error(f"Text parsing error: {e}")
        await update.message.reply_text(
            "Format teks salah. Sila guna format:\n"
            "Tarikh, Masa, Kedai, Senarai item; Jumlah item; Jumlah harga\n"
            "Contoh:\n2025-05-17, 10:30, Kedai ABC, Nasi Lemak 2 RM6.00; 2; 6.00"
        )

# --- WEBHOOK ROUTE ---

@app.route(f"/{TOKEN_BOT1}", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(application.update_queue.put(update), loop)
        return "OK"
    else:
        abort(405)

# --- REGISTER HANDLERS ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# --- MAIN ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
