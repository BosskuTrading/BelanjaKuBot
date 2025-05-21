import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def save_expense_to_sheet(data):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("Laporan Belanja").sheet1

        sheet.append_row([
            data.get("timestamp", ""),
            data.get("from", ""),
            data.get("chat_id", ""),
            data.get("item", ""),
            data.get("location", ""),
            data.get("amount", "")
        ])
    except Exception as e:
        print(f"[Ralat Google Sheets]: {e}")
