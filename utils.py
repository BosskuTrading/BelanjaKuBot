import pytesseract
from PIL import Image
import io
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

SHEET_ID = os.getenv("SHEET_ID")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'credentials.json'

def extract_text(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image)
    return text

def append_to_sheet(data):
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    range_ = 'Belanja!A:G'  # Sheet name
    body = {'values': [data]}
    result = sheet.values().append(
        spreadsheetId=SHEET_ID,
        range=range_,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

def parse_receipt(text):
    now = datetime.now()
    # Logik asas, boleh ditambah baik
    return [
        now.strftime('%Y-%m-%d'),  # Tarikh upload
        "Unknown Shop",            # Nama kedai
        "Unknown Time",            # Waktu
        "Unknown Location",        # Lokasi
        "Item A, Item B",          # Item
        "2",                       # Jumlah item
        "20.00"                    # Jumlah RM
    ]
