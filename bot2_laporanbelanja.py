import os
import logging
from telegram import Bot
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sheets_utils import get_sheet

# -------------------------------
# Muat token dan tetapan dari .env
# -------------------------------
load_dotenv()
TOKEN = os.getenv("TOKEN_BOT2")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")  # ID Telegram pengguna untuk terima laporan
SHEET_NAME = "Belanja"

bot = Bot(token=TOKEN)
logging.basicConfig(level=logging.INFO)

# -------------------------------
# Fungsi untuk jana ringkasan belanja
# -------------------------------
def generate_summary(period="daily"):
    """
    Baca data dari Google Sheet dan jumlahkan belanja.
    period: 'daily', 'weekly', 'monthly'
    """
    sheet = get_sheet()
    data = sheet.get_all_records()
    total = 0
    sekarang = datetime.now()

    if period == "daily":
        mula = sekarang.date()
        label = "Hari Ini"
    elif period == "weekly":
        mula = (sekarang - timedelta(days=7)).date()
        label = "Minggu Ini"
    elif period == "monthly":
        mula = sekarang.replace(day=1).date()
        label = "Bulan Ini"
    else:
        return None

    for baris in data:
        try:
            tarikh = datetime.strptime(baris["Tarikh"], "%Y-%m-%d %H:%M:%S").date()
            if tarikh >= mula:
                total += float(baris.get("Jumlah (RM)", 0))
        except:
            continue

    return f"📊 Laporan Perbelanjaan {label}:\nJumlah: RM{total:.2f}"

# -------------------------------
# Fungsi untuk hantar laporan kepada pengguna
# -------------------------------
def send_report():
    """Hantar ucapan mesra dan laporan ke Telegram."""
    ucapan = (
        "Salam sejahtera dari *LaporanBelanjaBot*!\n\n"
        "Saya bantu anda pantau perbelanjaan supaya lebih bijak mengurus kewangan.\n"
        "Berikut ialah ringkasan belanja terkini:\n"
    )
    bot.send_message(chat_id=USER_CHAT_ID, text=ucapan, parse_mode="Markdown")

    for tempoh in ["daily", "weekly", "monthly"]:
        ringkasan = generate_summary(tempoh)
        if ringkasan:
            bot.send_message(chat_id=USER_CHAT_ID, text=ringkasan)

# -------------------------------
# Fungsi utama (dipanggil oleh CRON)
# -------------------------------
if __name__ == "__main__":
    logging.info("LaporanBelanjaBot sedang menghantar laporan...")
    send_report()
