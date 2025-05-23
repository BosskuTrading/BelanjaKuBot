
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS_JSON tidak dijumpai dalam Environment Variables.")

    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Laporan Belanja").worksheet(sheet_name)

def save_expense_to_sheet(data):
    try:
        sheet = get_sheet("Laporan Belanja")
        sheet.append_row([
            data.get("timestamp", ""),
            data.get("from", ""),
            data.get("item", ""),
            data.get("location", ""),
            data.get("amount", ""),
            "",  # gambar placeholder
            data.get("chat_id", "")
        ])
    except Exception as e:
        print(f"[Sheet Error - save_expense_to_sheet]: {e}")

def get_all_users():
    try:
        sheet = get_sheet("Pengguna")
        return sheet.get_all_records()
    except Exception as e:
        print(f"[Sheet Error - get_all_users]: {e}")
        return []

def get_user_expenses(chat_id):
    try:
        sheet = get_sheet("Laporan Belanja")
        rows = sheet.get_all_values()[1:]
        user_expenses = [r for r in rows if r[-1] == str(chat_id)]
        return user_expenses
    except Exception as e:
        print(f"[Sheet Error - get_user_expenses]: {e}")
        return []
