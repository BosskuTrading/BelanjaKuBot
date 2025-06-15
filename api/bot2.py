import os
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Bot
import gspread
from sheets_utils import get_gspread_client

app = Flask(__name__)
TOKEN = os.getenv("TOKEN_BOT2")
SHEET_ID = os.getenv("SHEET_ID")
bot = Bot(token=TOKEN)

# Format mesej laporan
def format_report(rows, title="Laporan"):
    total = 0
    count = 0
    for row in rows:
        try:
            jumlah = float(row[6])
            total += jumlah
            count += 1
        except:
            continue
    return (
        f"📊 *{title}*\n"
        f"Transaksi: {count}\n"
        f"Jumlah belanja: RM{total:.2f}\n\n"
        "_Bot ini dibawakan oleh Fadirul Ezwan._"
    )

# Penapis ikut jenis laporan
def filter_by_date(rows, jenis):
    now = datetime.now()
    if jenis == "daily":
        target = now.date()
        return [r for r in rows if parse_date(r[0]) == target]
    elif jenis == "weekly":
        week_ago = now - timedelta(days=7)
        return [r for r in rows if parse_date(r[0]) >= week_ago.date()]
    elif jenis == "monthly":
        month_ago = now - timedelta(days=30)
        return [r for r in rows if parse_date(r[0]) >= month_ago.date()]
    return []

def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except:
        return None

@app.route("/bot2", methods=["GET"])
def send_reports():
    jenis = request.args.get("type", "daily")  # default harian
    title_map = {"daily": "Laporan Harian", "weekly": "Laporan Mingguan", "monthly": "Laporan Bulanan"}
    title = title_map.get(jenis, "Laporan")

    try:
        gc = get_gspread_client()
        sheet = gc.open_by_key(SHEET_ID)
        worksheets = sheet.worksheets()

        for ws in worksheets:
            chat_id = ws.title
            rows = ws.get_all_values()[1:]  # skip header
            filtered = filter_by_date(rows, jenis)

            if not filtered:
                continue

            msg = format_report(filtered, title)
            try:
                bot.send_message(chat_id=int(chat_id), text=msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Gagal hantar ke {chat_id}: {e}")
    except Exception as e:
        return f"❌ Gagal: {str(e)}", 500

    return "✅ Laporan dihantar", 200
