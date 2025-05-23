import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet(sheet_name):
    """
    Akses worksheet berdasarkan nama tab dalam Google Sheets 'Laporan Belanja'.
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    return client.open("Laporan Belanja").worksheet(sheet_name)

def save_expense_to_sheet(data):
    """
    Simpan satu rekod belanja ke tab 'Laporan Belanja'.
    """
    try:
        sheet = get_sheet("Laporan Belanja")
        sheet.append_row([
            data.get("timestamp", ""),
            data.get("from", ""),
            data.get("item", ""),
            data.get("location", ""),
            data.get("amount", ""),
            "",  # tempat simpan gambar jika perlu
            data.get("chat_id", "")
        ])
    except Exception as e:
        print(f"[Sheet Error - save_expense_to_sheet]: {e}")

def get_all_users():
    """
    Dapatkan semua pengguna dari tab 'Pengguna'.
    """
    try:
        sheet = get_sheet("Pengguna")
        return sheet.get_all_records()
    except Exception as e:
        print(f"[Sheet Error - get_all_users]: {e}")
        return []

def get_user_expenses(chat_id):
    """
    Dapatkan semua belanja berdasarkan chat_id dari tab 'Laporan Belanja'.
    """
    try:
        sheet = get_sheet("Laporan Belanja")
        rows = sheet.get_all_values()[1:]  # skip tajuk
        user_expenses = [r for r in rows if r[-1] == str(chat_id)]
        return user_expenses
    except Exception as e:
        print(f"[Sheet Error - get_user_expenses]: {e}")
        return []
