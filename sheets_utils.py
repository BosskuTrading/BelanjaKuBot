import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Pastikan SHEET_ID anda betul
SHEET_ID = os.getenv("SHEET_ID")
SHEET_NAME = "Belanja"

def get_sheet():
    """Sambung ke Google Sheet dan dapatkan worksheet."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    
    try:
        worksheet = sheet.worksheet(SHEET_NAME)
    except:
        worksheet = sheet.add_worksheet(title=SHEET_NAME, rows="1000", cols="10")
        worksheet.append_row(["Tarikh", "Nama", "Item", "Lokasi", "Jumlah (RM)", "Gambar"])

    return worksheet

def save_expense_to_sheet(data):
    """
    Simpan satu rekod belanja ke dalam Google Sheet.
    `data` mestilah dict dengan key: timestamp, from, item, location, amount, (optional: image_path)
    """
    worksheet = get_sheet()

    row = [
        data.get("timestamp", ""),
        data.get("from", ""),
        data.get("item", ""),
        data.get("location", ""),
        data.get("amount", ""),
        data.get("image_path", "")
    ]

    worksheet.append_row(row)
