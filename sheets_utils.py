import os
import json
import base64
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_BELANJA = "Belanja"
SHEET_PENGGUNA = "Pengguna"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_credentials():
    json_data = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not json_data:
        base64_data = os.getenv("GOOGLE_CREDENTIALS_BASE64")
        if base64_data:
            json_data = base64.b64decode(base64_data).decode("utf-8")
    return json.loads(json_data)

def get_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(get_credentials(), scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)

def get_or_create(name):
    sheet = get_sheet()
    try:
        return sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows="100", cols="20")
        if name == SHEET_BELANJA:
            ws.append_row(["Tarikh", "Item", "Tempat", "Jumlah (RM)", "Dari (Nama)", "Chat ID"])
        elif name == SHEET_PENGGUNA:
            ws.append_row(["Nama", "ChatID"])
        return ws

def save_expense_to_sheet(data):
    sheet = get_or_create(SHEET_BELANJA)
    sheet.append_row([
        data["timestamp"],
        data["item"],
        data["location"],
        data["amount"],
        data["from"],
        data["chat_id"]
    ])
    print("✅ Disimpan ke Google Sheet:", data)  # Log ini akan muncul di Render log

    # Juga log pengguna
    save_user_info(data["from"], data["chat_id"])

def save_user_info(name, chat_id):
    sheet = get_or_create(SHEET_PENGGUNA)
    existing = sheet.col_values(2)
    if str(chat_id) not in existing:
        sheet.append_row([name, str(chat_id)])
        print(f"👤 Pengguna baru direkod: {name} ({chat_id})")
