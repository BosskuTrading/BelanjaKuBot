
import os
import gspread
import base64
import json
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

def get_credentials():
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not credentials_json:
        decoded = base64.b64decode(os.getenv("GOOGLE_CREDENTIALS_BASE64")).decode("utf-8")
        credentials_json = decoded
    return json.loads(credentials_json)

def connect_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = get_credentials()
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet_id = os.getenv("SPREADSHEET_ID")
    return client.open_by_key(sheet_id)

def save_expense_to_sheet(data):
    try:
        sheet = connect_sheet()
        worksheet = sheet.worksheet("Laporan Belanja")
        row = [
            data.get("timestamp", ""),
            data.get("from", ""),
            data.get("item", ""),
            data.get("location", ""),
            data.get("amount", ""),
            "",  # Untuk gambar jika ada di masa depan
            data.get("chat_id", "")
        ]
        print("[DEBUG] Menulis baris ke Google Sheet:", row)
        worksheet.append_row(row)
        print("[DEBUG] Baris berjaya ditulis.")
    except Exception as e:
        print("[ERROR] Gagal simpan ke Google Sheets:", e)

def get_user_expenses(chat_id):
    try:
        sheet = connect_sheet()
        worksheet = sheet.worksheet("Laporan Belanja")
        data = worksheet.get_all_values()[1:]  # skip header
        return [row for row in data if len(row) > 6 and str(row[6]) == str(chat_id)]
    except Exception as e:
        print("[ERROR] Gagal baca data Google Sheets:", e)
        return []
