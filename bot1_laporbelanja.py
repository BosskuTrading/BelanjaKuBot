import os
import base64
import json
import logging
import re
from fastapi import FastAPI, Request, HTTPException
from telegram import Bot, Update
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import vision_v1
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT1_TOKEN = os.getenv("BOT1_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

if not all([BOT1_TOKEN, SPREADSHEET_ID, GOOGLE_CREDENTIALS_BASE64]):
    raise Exception("Missing environment variables: BOT1_TOKEN, SPREADSHEET_ID, or GOOGLE_CREDENTIALS_BASE64")

# Decode Google credentials
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
credentials_info = json.loads(credentials_json)
credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/cloud-platform",
    ],
)

# Setup Google Sheets API
sheets_service = build("sheets", "v4", credentials=credentials)
sheet = sheets_service.spreadsheets()

# Setup Google Vision client (OCR)
vision_client = vision_v1.ImageAnnotatorClient(credentials=credentials)

app = FastAPI()
bot = Bot(token=BOT1_TOKEN)
application = Application.builder().token(BOT1_TOKEN).build()

def append_to_sheet(row_values):
    try:
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Sheet1!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [row_values]},
        ).execute()
        logger.info(f"Appended to sheet: {row_values}")
    except HttpError as e:
        logger.error(f"Google Sheets API error: {e}")

def parse_date(text):
    # Try to extract date in formats like YYYY-MM-DD or DD/MM/YYYY
    date_patterns = [
        r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",  # 2023-05-17 or 2023/05/17
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})",  # 17-05-2023 or 17/05/2023
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""

def parse_amount(text):
    # Simple regex to find amounts like 12.34, 1,234.56 or 1234.56
    amount_patterns = [
        r"\b(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b",  # Matches 1,234.56 or 1234.56
        r"\b(\d+\.\d{2})\b",  # Matches 12.34
    ]
    for pattern in amount_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # Ambil nilai max sebab biasanya jumlah besar
            try:
                nums = [float(m.replace(",", "")) for m in matches]
                return f"{max(nums):.2f}"
            except:
                continue
    return ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or "there"
    welcome_msg = (
        f"Hai {user_first_name}! 👋\n\n"
        "Saya bot pelacak belanja anda.\n"
        "Hantarkan gambar resit pembelian untuk saya ekstrak maklumat belanja.\n"
        "Taip /help untuk panduan penggunaan.\n"
        "Taip /status untuk semak berapa resit anda telah hantar."
    )
    await update.message.reply_text(welcome_msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "Cara guna bot ini:\n"
        "1. Hantar gambar resit pembelian.\n"
        "2. Saya akan cuba ekstrak maklumat dan simpan ke Google Sheets.\n"
        "3. Anda boleh semak laporan bulanan melalui bot laporan nanti.\n\n"
        "Jika ada masalah, hubungi admin."
    )
    await update.message.reply_text(help_msg)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        # Query Google Sheets untuk kira berapa rekod ada utk chat_id ini
        range_ = "Sheet1!A:A"
        result = (
            sheet.values()
            .get(spreadsheetId=SPREADSHEET_ID, range=range_)
            .execute()
        )
        values = result.get("values", [])
        count = sum(1 for row in values if row and row[0] == str(chat_id))
        await update.message.reply_text(
            f"Anda telah menghantar {count} resit kepada saya. Terima kasih! 👍"
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        await update.message.reply_text(
            "Maaf, saya tidak dapat semak status anda sekarang."
        )

def perform_ocr(image_bytes):
    image = vision_v1.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = update.message.photo
    if not photos:
        await update.message.reply_text(
            "Maaf, gambar tidak ditemui. Sila cuba hantar semula."
        )
        return

    photo_file = photos[-1]  # resolusi tertinggi
    file = await context.bot.get_file(photo_file.file_id)
    image_bytes = await file.download_as_bytearray()

    text_detected = perform_ocr(image_bytes)
    if not text_detected.strip():
        await update.message.reply_text(
            "Maaf, saya tidak dapat membaca resit. Sila cuba gambar yang lebih jelas."
        )
        return

    # Cuba parse tarikh dan jumlah
    tarikh = parse_date(text_detected)
    jumlah = parse_amount(text_detected)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = [str(update.effective_chat.id), now_str, tarikh, jumlah, text_detected[:500]]
    append_to_sheet(row)

    reply_msg = (
        "✅ Resit anda telah direkodkan!\n"
        f"🗓 Tarikh (jika dapat dikesan): {tarikh or '-'}\n"
        f"💰 Jumlah (jika dapat dikesan): {jumlah or '-'}\n\n"
        "Terima kasih kerana menggunakan bot ini.\n"
        "Taip /status untuk semak jumlah resit anda."
    )
    await update.message.reply_text(reply_msg)

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("status", status_command))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

@app.post(f"/{BOT1_TOKEN}")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        await application.update_queue.put(update)
        await application.process_update()
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        raise HTTPException(status_code=400, detail="Failed to process update")
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Bot1 LaporBelanja is running."}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
