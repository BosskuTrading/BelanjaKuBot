import os
import base64
import json
import datetime
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

BOT2_TOKEN = os.getenv('BOT2_TOKEN')
SHEET_ID = os.getenv('SHEET_ID')
GOOGLE_CREDENTIALS_BASE64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')

# Decode credentials JSON from base64 env
credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64)
credentials = Credentials.from_service_account_info(json.loads(credentials_json))

service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

bot = Bot(token=BOT2_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0)

def start(update, context):
    update.message.reply_text(
        "Selamat datang ke LaporanBelanjaBot!\n"
        "Gunakan /laporan untuk dapatkan laporan perbelanjaan mingguan dan bulanan anda."
    )

def get_user_expenses(chat_id):
    # Contoh: Tarik data dari sheet
    # Anggap sheet simpan dengan kolom: chat_id | date | shop | total_amount
    result = sheet.values().get(spreadsheetId=SHEET_ID, range="Sheet1!A2:D").execute()
    rows = result.get('values', [])
    user_data = []
    for row in rows:
        if len(row) < 4:
            continue
        row_chat_id = row[0]
        if str(row_chat_id) == str(chat_id):
            user_data.append({
                'date': row[1],
                'shop': row[2],
                'total_amount': float(row[3])
            })
    return user_data

def laporan(update, context):
    chat_id = update.message.chat_id
    data = get_user_expenses(chat_id)
    if not data:
        update.message.reply_text("Tiada rekod perbelanjaan anda ditemui.")
        return
    
    today = datetime.date.today()
    one_week_ago = today - datetime.timedelta(days=7)
    one_month_ago = today - datetime.timedelta(days=30)
    
    # Kira jumlah perbelanjaan mingguan & bulanan
    weekly_total = sum(d['total_amount'] for d in data if datetime.datetime.strptime(d['date'], '%Y-%m-%d').date() >= one_week_ago)
    monthly_total = sum(d['total_amount'] for d in data if datetime.datetime.strptime(d['date'], '%Y-%m-%d').date() >= one_month_ago)

    message = (
        f"Laporan Perbelanjaan Anda:\n\n"
        f"Jumlah perbelanjaan minggu lalu: RM {weekly_total:.2f}\n"
        f"Jumlah perbelanjaan bulan ini: RM {monthly_total:.2f}\n"
        f"Terima kasih menggunakan LaporBelanjaBot!"
    )
    update.message.reply_text(message)

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('laporan', laporan))

@app.route(f'/{BOT2_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

@app.route('/')
def index():
    return 'LaporanBelanjaBot running.'

if __name__ == '__main__':
    app.run(port=10001)
