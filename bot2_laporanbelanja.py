# bot2_laporanbelanja.py

import os
import json
import base64
import logging
from datetime import datetime, timedelta
from telegram import Bot
import gspread

# Logging
logging.basicConfig(level=logging.INFO)

# Token & Sheet
BOT_TOKEN = os.getenv("TOKEN_BOT2")
SHEET_ID = os.getenv("SHEET_ID")

# Setup bot
bot = Bot(BOT_TOKEN)

# Google Sheets auth
creds_json = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_BASE64"]).decode("utf-8")
creds_dict = json.loads(creds_json)
gc = gspread.service_account_from_dict(creds_dict)
sheet = gc.open_by_key(SHEET_ID).sheet1


def get_all_data():
    rows = sheet.get_all_values()[1:]  # skip header
    headers = sheet.row_values(1)
    return [dict(zip(headers, row)) for row in rows]


def filter_by_date(data, start_date, end_date):
    return [row for row in data if start_date <= row.get("date", "") <= end_date]


def group_by_user(data):
    grouped = {}
    for row in data:
        chat_id = row.get("user_id")
        if chat_id not in grouped:
            grouped[chat_id] = []
        grouped[chat_id].append(row)
    return grouped


def summarize_expenses(rows):
    try:
        total = sum(float(row.get("amount", 0)) for row in rows)
        count = len(rows)
    except:
        total, count = 0, 0
    return total, count


def send_report_to_user(chat_id, title, rows):
    total, count = summarize_expenses(rows)
    if count =
