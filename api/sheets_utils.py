import base64
import json
import os
from io import BytesIO
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

# Load Google Credentials from base64 env
def get_gspread_client():
    base64_creds = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    if not base64_creds:
        raise Exception("Missing GOOGLE_CREDENTIALS_BASE64 environment variable.")
    
    creds_json = base64.b64decode(base64_creds).decode("utf-8")
    creds_dict = json.loads(creds_json)
    
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(credentials)

# Get worksheet by chat_id
def get_or_create_user_worksheet(sheet, chat_id: str):
    try:
        return sheet.worksheet(chat_id)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=chat_id, rows="1000", cols="10")
        worksheet.append_row(["Tarikh", "Masa", "Lokasi", "Kedai", "Item", "Jumlah Item", "Jumlah (RM)", "Nota", "Imej URL"])
        return worksheet

# Simpan satu rekod belanja
def save_expense(chat_id, data: dict):
    gc = get_gspread_client()
    sheet_id = os.getenv("SHEET_ID")
    sheet = gc.open_by_key(sheet_id)
    
    ws = get_or_create_user_worksheet(sheet, str(chat_id))

    row = [
        data.get("tarikh") or datetime.now().strftime("%Y-%m-%d"),
        data.get("masa") or datetime.now().strftime("%H:%M"),
        data.get("lokasi") or "",
        data.get("kedai") or "",
        data.get("item") or "",
        data.get("jumlah_item") or "",
        data.get("jumlah") or "",
        data.get("nota") or "",
        data.get("image_url") or ""
    ]

    ws.append_row(row, value_input_option="USER_ENTERED")
