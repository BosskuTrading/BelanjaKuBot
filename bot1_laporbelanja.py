import os
import io
import base64
import logging
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import vision
import requests
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Environment variables
BOT_TOKEN = os.getenv('BOT1_TOKEN')
TELEGRAM_API_URL = f'https://api.telegram.org/bot{BOT_TOKEN}'
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
GOOGLE_CREDENTIALS_BASE64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')

if not (BOT_TOKEN and SPREADSHEET_ID and GOOGLE_CREDENTIALS_BASE64):
    raise Exception("Missing environment variables: BOT1_TOKEN, SPREADSHEET_ID, or GOOGLE_CREDENTIALS_BASE64")

# Decode Google credentials from base64 env var
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
with open('credentials.json', 'wb') as f:
    f.write(credentials_json)

credentials = service_account.Credentials.from_service_account_file('credentials.json')
sheets_service = build('sheets', 'v4', credentials=credentials)

# Vision client
vision_client = vision.ImageAnnotatorClient.from_service_account_file('credentials.json')

def send_message(chat_id, text):
    url = TELEGRAM_API_URL + '/sendMessage'
    payload = {'chat_id': chat_id, 'text': text}
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        logging.error(f'Failed to send message: {resp.text}')
    return resp

def extract_text_from_image(file_bytes):
    image = vision.Image(content=file_bytes)
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations
    if response.error.message:
        logging.error(f"Vision API error: {response.error.message}")
        return ""
    if texts:
        return texts[0].description
    return ""

def parse_expense(text):
    """
    Cuba parsing kasar dari teks OCR untuk cari tarikh, total amount, kedai.
    Ini contoh sangat mudah, boleh tambah regex lebih advanced.
    """
    import re

    # Cari tarikh (simple format dd/mm/yyyy atau dd-mm-yyyy)
    date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
    date_str = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')

    # Cari jumlah total (cari nombor dengan tanda titik atau koma)
    amount_match = re.findall(r'(\d+[.,]\d{2})', text)
    total_amount = amount_match[-1] if amount_match else '0.00'

    # Kedai: ambil baris pertama teks sebagai kedai (simple)
    store = text.split('\n')[0].strip() if text else 'Unknown Store'

    return date_str, store, total_amount

def append_to_sheet(row_values):
    body = {'values': [row_values]}
    sheet = sheets_service.spreadsheets().values()
    result = sheet.append(spreadsheetId=SPREADSHEET_ID,
                          range='Expenses!A:D',
                          valueInputOption='USER_ENTERED',
                          body=body).execute()
    logging.info(f"Appended to sheet: {row_values}")
    return result

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = request.get_json(force=True)
        logging.info(f"Update received: {update}")

        message = update.get('message')
        if not message:
            return jsonify({'status': 'no message'}), 200

        chat_id = message['chat']['id']
        text = message.get('text')
        photos = message.get('photo')

        if text == '/start':
            send_message(chat_id, "Selamat datang ke LaporBelanjaBot! Hantar gambar resit untuk direkod.")
            return jsonify({'status': 'ok'}), 200

        if photos:
            # Dapatkan file_id photo terbesar (resolusi tertinggi)
            photo_file = photos[-1]
            file_id = photo_file['file_id']

            # Dapatkan file_path dari Telegram
            file_info_url = TELEGRAM_API_URL + f'/getFile?file_id={file_id}'
            file_info = requests.get(file_info_url).json()
            file_path = file_info['result']['file_path']

            # Download file
            file_url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}'
            file_response = requests.get(file_url)
            file_bytes = file_response.content

            # Extract text dari gambar
            ocr_text = extract_text_from_image(file_bytes)
            logging.info(f"OCR Text:\n{ocr_text}")

            # Parse data kasar
            date_str, store, total_amount = parse_expense(ocr_text)

            # Simpan ke Google Sheets
            append_to_sheet([date_str, store, total_amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])

            reply_text = f"Terima kasih! Resit dari '{store}' dengan jumlah RM {total_amount} telah direkod."
            send_message(chat_id, reply_text)
            return jsonify({'status': 'ok'}), 200

        else:
            send_message(chat_id, "Sila hantar gambar resit untuk direkod.")
            return jsonify({'status': 'no photo'}), 200

    except Exception as e:
        logging.error(f"Webhook error: {e}")
        send_message(chat_id, "Maaf, berlaku ralat dalam proses. Sila cuba lagi.")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # Run Flask di localhost port 10000 (Render nanti set environment variable PORT)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
