import os
import base64
import json
import logging
from fastapi import FastAPI, Request, HTTPException
from telegram import Bot, Update
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import vision_v1
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT1_TOKEN = os.getenv("BOT1_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")

if not all([BOT1_TOKEN, SPREADSHEET_ID, GOOGLE_CREDENTIALS_BASE64]):
    raise Exception("Missing environment variables: BOT1_TOKEN, SPREADSHEET_ID, or GOOGLE_CREDENTIALS_BASE64")

# Decode Google credentials JSON from base64 env var
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
credentials_info = json.loads(credentials_json)
credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/cloud-platform"]
)

# Setup Google Sheets API client
sheets_service = build('sheets', 'v4', credentials=credentials)
sheet = sheets_service.spreadsheets()

# Setup Google Vision client (OCR)
vision_client = vision_v1.ImageAnnotatorClient(credentials=credentials)

app = FastAPI()
bot = Bot(token=BOT1_TOKEN)
application = Application.builder().token(BOT1_TOKEN).build()

# Utility function to append a row to Google Sheets
def append_to_sheet(row_values):
    try:
        result = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Sheet1!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [row_values]}
        ).execute()
        logger.info(f"Appended to sheet: {row_values}")
    except HttpError as e:
        logger.error(f"Google Sheets API error: {e}")

# Command handler /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or "there"
    welcome_msg = (
        f"Hai {user_first_name}! 👋\n\n"
        "Saya bot pelacak belanja anda.\n"
        "Hantarkan gambar resit pembelian untuk saya ekstrak maklumat belanja.\n"
        "Atau taip /help untuk panduan penggunaan."
    )
    await update.message.reply_text(welcome_msg)

# Command handler /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "Cara guna bot ini:\n"
        "1. Hantar gambar resit pembelian.\n"
        "2. Saya akan cuba ekstrak maklumat dan simpan ke Google Sheets.\n"
        "3. Anda boleh semak laporan bulanan melalui bot laporan nanti.\n\n"
        "Jika ada masalah, hubungi admin."
    )
    await update.message.reply_text(help_msg)

# Function to do OCR on image bytes
def perform_ocr(image_bytes):
    image = vision_v1.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

# Handler for photo messages (receipt images)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    photos = update.message.photo
    if not photos:
        await update.message.reply_text("Maaf, gambar tidak ditemui. Sila cuba hantar semula.")
        return
    
    photo_file = photos[-1]  # dapatkan gambar resolusi tertinggi
    file = await context.bot.get_file(photo_file.file_id)
    image_bytes = await file.download_as_bytearray()

    # Jalankan OCR pada gambar
    text_detected = perform_ocr(image_bytes)
    if not text_detected.strip():
        await update.message.reply_text("Maaf, saya tidak dapat membaca resit. Sila cuba gambar yang lebih jelas.")
        return
    
    # Simpan rekod ke Google Sheets (contoh sahaja, hanya tarikh + chat_id + teks penuh)
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [str(chat_id), now_str, text_detected[:500]]  # limit 500 char teks
    append_to_sheet(row)
    
    await update.message.reply_text(
        "Terima kasih! Resit anda telah direkodkan.\n"
        "Saya akan cuba ekstrak maklumat dengan lebih baik pada masa hadapan."
    )

# Register handlers to application
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

# FastAPI webhook route
@app.post(f"/{BOT1_TOKEN}")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    await application.update_queue.put(update)
    await application.process_updates()
    return {"status": "ok"}

# Root route for health check
@app.get("/")
async def root():
    return {"message": "Bot1 LaporBelanja is running."}

# Run command (optional for local dev only)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
