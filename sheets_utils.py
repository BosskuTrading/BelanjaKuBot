import os
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Baca ID spreadsheet
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise RuntimeError("SPREADSHEET_ID tidak dijumpai di environment")

# Baca credential Google dari JSON atau Base64
creds_json    = os.getenv("GOOGLE_CREDENTIALS_JSON")
creds_b64     = os.getenv("GOOGLE_CREDENTIALS_BASE64")
if creds_json:
    info = json.loads(creds_json)
elif creds_b64:
    info = json.loads(base64.b64decode(creds_b64))
else:
    raise RuntimeError("Sila tetapkan GOOGLE_CREDENTIALS_JSON atau GOOGLE_CREDENTIALS_BASE64")

# Scope dan authorize
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(info, SCOPES)
client = gspread.authorize(creds)

SHEET_BELANJA = "Belanja"
SHEET_PENGGUNA = "Pengguna"

def get_or_create(ws_name, headers):
    sh = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet(ws_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=ws_name, rows="1000", cols=str(len(headers)))
        ws.append_row(headers)
    return ws

def save_expense_to_sheet(data):
    # Simpan Belanja
    ws = get_or_create(SHEET_BELANJA, ["Tarikh","Nama","Item","Lokasi","Jumlah (RM)","Gambar","ChatID"])
    ws.append_row([
        data.get("timestamp",""),
        data.get("from",""),
        data.get("item",""),
        data.get("location",""),
        data.get("amount",""),
        data.get("image_path",""),
        data.get("chat_id","")
    ])

    # Simpan pengguna
    ws_u = get_or_create(SHEET_PENGGUNA, ["Nama","ChatID"])
    all_users = {r["ChatID"] for r in ws_u.get_all_records()}
    cid = str(data["chat_id"])
    if cid not in all_users:
        ws_u.append_row([data["from"], cid])

def get_all_users():
    ws_u = get_or_create(SHEET_PENGGUNA, ["Nama","ChatID"])
    return ws_u.get_all_records()

def get_user_expenses(chat_id):
    ws = get_or_create(SHEET_BELANJA, ["Tarikh","Nama","Item","Lokasi","Jumlah (RM)","Gambar","ChatID"])
    return [r for r in ws.get_all_records() if str(r.get("ChatID")) == str(chat_id)]
