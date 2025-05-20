import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = os.getenv("SHEET_ID")
SHEET_BELANJA = "Belanja"
SHEET_PENGGUNA = "Pengguna"

def get_client():
    """Sambung ke Google Sheets API."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

def get_or_create_worksheet(sheet, name, headers):
    try:
        ws = sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="10")
        ws.append_row(headers)
    return ws

def save_expense_to_sheet(data):
    """
    Simpan data belanja ke worksheet 'Belanja' & simpan pengguna ke 'Pengguna'
    Data perlu ada: timestamp, from, item, location, amount, chat_id, image_path (optional)
    """
    client = get_client()
    sheet = client.open_by_key(SHEET_ID)

    # Simpan perbelanjaan
    ws_belanja = get_or_create_worksheet(sheet, SHEET_BELANJA,
        ["Tarikh", "Nama", "Item", "Lokasi", "Jumlah (RM)", "Gambar", "ChatID"])
    row = [
        data.get("timestamp", ""),
        data.get("from", ""),
        data.get("item", ""),
        data.get("location", ""),
        data.get("amount", ""),
        data.get("image_path", ""),
        data.get("chat_id", "")
    ]
    ws_belanja.append_row(row)

    # Simpan pengguna jika belum ada
    ws_user = get_or_create_worksheet(sheet, SHEET_PENGGUNA, ["Nama", "ChatID"])
    existing_ids = [r[1] for r in ws_user.get_all_values()[1:] if len(r) > 1]
    if str(data["chat_id"]) not in existing_ids:
        ws_user.append_row([data["from"], str(data["chat_id"])])

def get_all_users():
    """Ambil semua pengguna berdaftar dari worksheet 'Pengguna'."""
    client = get_client()
    sheet = client.open_by_key(SHEET_ID)
    ws_user = get_or_create_worksheet(sheet, SHEET_PENGGUNA, ["Nama", "ChatID"])
    return ws_user.get_all_records()

def get_user_expenses(chat_id):
    """Ambil semua rekod belanja bagi satu chat_id."""
    client = get_client()
    sheet = client.open_by_key(SHEET_ID)
    ws_belanja = get_or_create_worksheet(sheet, SHEET_BELANJA,
        ["Tarikh", "Nama", "Item", "Lokasi", "Jumlah (RM)", "Gambar", "ChatID"])
    return [r for r in ws_belanja.get_all_records() if str(r.get("ChatID", "")) == str(chat_id)]
