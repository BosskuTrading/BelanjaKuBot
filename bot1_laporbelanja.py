import os
import base64
import logging
import io
import json
from datetime import datetime
from flask import Flask, request
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image
import pytesseract

# --- CONFIG ---
BOT_TOKEN = os.getenv('BOT1_TOKEN')
GOOGLE_CREDENTIALS_BASE64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
SHEET_ID = '1h2br8RSuvuNVydz-4sKXalziottO4QHwtSVP8v1RECQ'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Google Sheets Setup ---
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
credentials = service_account.Credentials.from_service_account_info(json.loads(credentials_json), scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# --- Flask App ---
app = Flask(__name__)

# --- States for ConversationHandler ---
(
    ASK_LOCATION,
    ASK_MORE_ITEMS,
    ASK_UPLOAD_IMAGE,
) = range(3)

# --- Temporary storage per user chat_id ---
user_data_temp = {}

# --- Helper functions ---

def save_to_sheet(row_values):
    """Append a row to Google Sheets."""
    body = {'values': [row_values]}
    result = sheet.values().append(
        spreadsheetId=SHEET_ID,
        range='Sheet1!A1',
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body=body
    ).execute()
    return result

def parse_text_expense(text):
    """
    Simple parser for text input like:
    'nasi ayam rm10.50'
    Return dict with keys: items, total_amount
    """
    import re
    # Extract total amount (e.g. rm10.50)
    amount_match = re.search(r'(?i)rm\s*([0-9]+(?:\.[0-9]{1,2})?)', text)
    total_amount = float(amount_match.group(1)) if amount_match else 0.0
    
    # Remove amount from text, assume remaining text is items description
    items_text = re.sub(r'(?i)rm\s*[0-9]+(?:\.[0-9]{1,2})?', '', text).strip()
    
    # We consider items separated by commas or "dan"
    items = [i.strip() for i in re.split(r',|dan', items_text) if i.strip()]
    
    return {
        'items': items,
        'total_amount': total_amount,
        'total_items': len(items)
    }

def ocr_image_expense(image_bytes):
    """Perform OCR on image bytes, try to extract structured data."""
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image, lang='eng+msa')
    
    # Simple heuristics to parse from OCR text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    date_str = None
    time_str = None
    location = None
    items = []
    total_amount = 0.0
    
    # Try to find date and time (common date formats)
    import re
    date_pattern = re.compile(r'(\d{2}[-/]\d{2}[-/]\d{4}|\d{4}[-/]\d{2}[-/]\d{2})')
    time_pattern = re.compile(r'(\d{2}:\d{2}(:\d{2})?)')
    
    for line in lines:
        if not date_str:
            d = date_pattern.search(line)
            if d:
                date_str = d.group(0)
        if not time_str:
            t = time_pattern.search(line)
            if t:
                time_str = t.group(0)
        if not location and len(line) > 3 and not re.search(r'[0-9]', line):
            # Guess location is first text line with no digits (heuristic)
            location = line
        
    # Assume last lines have total amount
    for line in reversed(lines):
        match = re.search(r'(?i)total\s*[:\-]?\s*rm?\s*([0-9]+(?:\.[0-9]{1,2})?)', line)
        if match:
            total_amount = float(match.group(1))
            break
    
    # Items detection: lines between location and total, ignoring date/time lines
    # This is heuristic, so just collect lines not date/time and not location/total
    for line in lines:
        if line not in [location, date_str, time_str]:
            if not re.search(r'total', line, re.I):
                # Filter lines that look like item lines
                if len(line) > 2 and not re.match(r'\d+[-/]\d+[-/]\d+', line):
                    items.append(line)
    
    total_items = len(items)
    
    # Format date/time
    try:
        if date_str:
            dt_obj = datetime.strptime(date_str, '%d-%m-%Y')
            date_str = dt_obj.strftime('%Y-%m-%d')
        if time_str:
            time_obj = datetime.strptime(time_str, '%H:%M')
            time_str = time_obj.strftime('%H:%M:%S')
    except Exception:
        # ignore parsing error
        pass
    
    return {
        'date': date_str or datetime.now().strftime('%Y-%m-%d'),
        'time': time_str or datetime.now().strftime('%H:%M:%S'),
        'location': location or 'Unknown',
        'items': items,
        'total_items': total_items,
        'total_amount': total_amount
    }

def save_image(chat_id, image_bytes):
    folder = 'saved_receipts'
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = f'{folder}/receipt_{chat_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'
    with open(filename, 'wb') as f:
        f.write(image_bytes)
    return filename

# --- Telegram Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = f"Salam! Saya LaporBelanjaBot.\n\n"\
                   f"Hantar maklumat belanja anda, sama ada teks atau gambar resit.\n"\
                   f"Contoh: 'Nasi ayam rm10.50'\n\n"\
                   f"Saya akan bantu anda simpan rekod perbelanjaan harian.\n"\
                   f"Gunakan /help untuk arahan lanjut."
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Arahan penggunaan:\n"
        "- Hantar teks belanja seperti 'nasi ayam rm10.50'.\n"
        "- Hantar gambar resit untuk diproses OCR.\n"
        "- Bot akan tanya lokasi jika tidak lengkap.\n"
        "- Anda boleh tambah item lain jika perlu.\n"
        "- Data akan disimpan ke Google Sheets secara automatik."
    )
    await update.message.reply_text(help_text)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip().lower()
    
    # Simpan sementara data parsed
    data = parse_text_expense(text)
    
    user_data_temp[chat_id] = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'location': None,
        'items': data['items'],
        'total_items': data['total_items'],
        'total_amount': data['total_amount'],
        'image_path': None,
    }
    
    await update.message.reply_text(
        f"Saya nampak anda belanja:\nItems: {', '.join(data['items'])}\nJumlah: RM {data['total_amount']:.2f}\n"
        f"Di mana lokasi/kedai belanja ni?"
    )
    
    return ASK_LOCATION

async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    location = update.message.text.strip()
    
    user_data_temp[chat_id]['location'] = location
    
    await update.message.reply_text(
        "Ada lagi barang lain ke yang anda nak tambah? (Ya/Tidak)"
    )
    return ASK_MORE_ITEMS

async def ask_more_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip().lower()
    
    if text in ['ya', 'y', 'yes']:
        await update.message.reply_text(
            "Sila taip barang tambahan (contoh: air mineral rm2.50):"
        )
        return ASK_MORE_ITEMS
    elif text in ['tidak', 't', 'no']:
        # Check if image already diberikan
        if user_data_temp[chat_id]['image_path'] is None:
            await update.message.reply_text(
                "Sila upload gambar resit untuk rekod lengkap (atau taip /skip jika tiada):"
            )
            return ASK_UPLOAD_IMAGE
        else:
            # Save all data to Google Sheets
            return await save_data_and_finish(update, context)
    else:
        # Assume user hantar barang tambahan text
        data = parse_text_expense(text)
        
        user_data_temp[chat_id]['items'].extend(data['items'])
        user_data_temp[chat_id]['total_items'] = len(user_data_temp[chat_id]['items'])
        user_data_temp[chat_id]['total_amount'] += data['total_amount']
        
        await update.message.reply_text(
            f"Tambah barang: {', '.join(data['items'])}\n"
            f"Jumlah terkini: RM {user_data_temp[chat_id]['total_amount']:.2f}\n"
            "Ada lagi barang lain?"
        )
        return ASK_MORE_ITEMS

async def ask_upload_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if update.message.photo:
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        filename = save_image(chat_id, photo_bytes)
        user_data_temp[chat_id]['image_path'] = filename
        
        await update.message.reply_text("Gambar resit telah disimpan. Terima kasih!")
        
        return await save_data_and_finish(update, context)
    elif update.message.text and update.message.text.lower() == '/skip':
        await update.message.reply_text("Data anda telah disimpan tanpa gambar resit. Terima kasih!")
        return await save_data_and_finish(update, context)
    else:
        await update.message.reply_text("Sila hantar gambar resit atau taip /skip jika tiada.")
        return ASK_UPLOAD_IMAGE

async def save_data_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    data = user_data_temp.get(chat_id)
    if not data:
        await update.message.reply_text("Tiada data untuk disimpan.")
        return ConversationHandler.END
    
    # Prepare row for Google Sheets
    row = [
        data['date'],
        data['time'],
        data['location'] or 'Unknown',
        ', '.join(data['items']),
        str(data['total_items']),
        f"{data['total_amount']:.2f}",
        f"{user.full_name} ({chat_id})"
    ]
    
    save_to_sheet(row)
    
    await update.message.reply_text("Rekod belanja anda telah disimpan ke Google Sheets. Terima kasih!")
    
    # Clear temp data
    user_data_temp.pop(chat_id, None)
    
    return ConversationHandler.END

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    # OCR process
    parsed = ocr_image_expense(photo_bytes)
    
    filename = save_image(chat_id, photo_bytes)
    
    user_data_temp[chat_id] = {
        'date': parsed.get('date', datetime.now().strftime('%Y-%m-%d')),
        'time': parsed.get('time', datetime.now().strftime('%H:%M:%S')),
        'location': parsed.get('location', 'Unknown'),
        'items': parsed.get('items', []),
        'total_items': parsed.get('total_items', 0),
        'total_amount': parsed.get('total_amount', 0.0),
        'image_path': filename,
    }
    
    await update.message.reply_text(
        f"Saya dah baca resit ini:\nTarikh: {user_data_temp[chat_id]['date']}\n"
        f"Masa: {user_data_temp[chat_id]['time']}\nLokasi: {user_data_temp[chat_id]['location']}\n"
        f"Items: {', '.join(user_data_temp[chat_id]['items'])}\n"
        f"Jumlah items: {user_data_temp[chat_id]['total_items']}\n"
        f"Jumlah belanja: RM {user_data_temp[chat_id]['total_amount']:.2f}\n\n"
        f"Betul tak? Kalau betul, saya akan simpan rekod ini. Kalau nak ubah, taip /cancel dan hantar semula."
    )
    
    # Simpan terus ke sheet sebab sudah ada gambar
    return await save_data_and_finish(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_data_temp:
        user_data_temp.pop(chat_id)
    await update.message.reply_text("Transaksi dibatalkan. Anda boleh mulakan semula.")
    return ConversationHandler.END

# --- Main function to run app and set webhook ---

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook_handler():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return 'OK'

async def set_webhook():
    webhook_url = f"https://laporbelanjabot.onrender.com/{BOT_TOKEN}"
    await application.bot.set_webhook(webhook_url)

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text),
                      MessageHandler(filters.PHOTO, handle_photo)],
        states={
            ASK_LOCATION: [MessageHandler(filters.TEXT & (~filters.COMMAND), ask_location)],
            ASK_MORE_ITEMS: [MessageHandler(filters.TEXT & (~filters.COMMAND), ask_more_items)],
            ASK_UPLOAD_IMAGE: [
                MessageHandler(filters.PHOTO, ask_upload_image),
                MessageHandler(filters.TEXT & (~filters.COMMAND), ask_upload_image)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(conv_handler)
    
    import asyncio
    asyncio.run(set_webhook())

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
