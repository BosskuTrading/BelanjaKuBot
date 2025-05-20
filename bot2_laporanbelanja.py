import os
import logging
from telegram import Bot
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sheets_utils import get_all_users, get_user_expenses

# -------------------------------
# Muat token dari .env
# -------------------------------
load_dotenv()
TOKEN = os.getenv("TOKEN_BOT2")

bot = Bot(token=TOKEN)
logging.basicConfig(level=logging.INFO)

# -------------------------------
# Fungsi kira jumlah belanja ikut tempoh
# -------------------------------
def kira_jumlah(data, period="daily"):
    jumlah = 0
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

    for rekod in data:
        try:
            tarikh = datetime.strptime(rekod["Tarikh"], "%Y-%m-%d %H:%M:%S").date()
            if tarikh >= mula:
                jumlah += float(rekod.get("Jumlah (RM)", 0))
        except:
            continue

    return label, jumlah

# -------------------------------
# Hantar laporan ke setiap pengguna
# -------------------------------
def hantar_laporan():
    pengguna = get_all_users()

    for user in pengguna:
        nama = user["Nama"]
        chat_id = user["ChatID"]
        data = get_user_expenses(chat_id)

        ucapan = (
            f"Hai {nama}!\n\n"
            "Ini ialah laporan perbelanjaan anda dari *LaporanBelanjaBot*.\n"
            "Saya bantu anda semak belanja dan urus kewangan lebih bijak.\n"
        )

        try:
            bot.send_message(chat_id=chat_id, text=ucapan, parse_mode="Markdown")

            for period in ["daily", "weekly", "monthly"]:
                label, jumlah = kira_jumlah(data, period)
                mesej = f"📊 Perbelanjaan {label}:\nJumlah: RM{jumlah:.2f}"
                bot.send_message(chat_id=chat_id, text=mesej)

        except Exception as e:
            logging.error(f"Gagal hantar ke {chat_id}: {e}")

# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    logging.info("LaporanBelanjaBot sedang menghantar laporan ke semua pengguna...")
    hantar_laporan()
