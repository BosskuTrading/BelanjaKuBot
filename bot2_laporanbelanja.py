import os
import logging
from telegram import Bot
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sheets_utils import get_all_users, get_user_expenses

# ──────────────────────────────────────────────────────────────────────────────
# Muat .env dan baca token dari BOT2_TOKEN
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("BOT2_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT2_TOKEN belum disetkan di environment!")

bot = Bot(token=TOKEN)
logging.basicConfig(level=logging.INFO)

# ──────────────────────────────────────────────────────────────────────────────
# Fungsi kira jumlah belanja bagi tempoh tertentu
# ──────────────────────────────────────────────────────────────────────────────
def calculate_summary(records, period: str):
    total = 0.0
    now = datetime.now()

    if period == "daily":
        start = now.date()
        label = "Hari Ini"
    elif period == "weekly":
        start = (now - timedelta(days=7)).date()
        label = "Minggu Ini"
    elif period == "monthly":
        start = now.replace(day=1).date()
        label = "Bulan Ini"
    else:
        return None, 0.0

    for r in records:
        try:
            ts = datetime.strptime(r["Tarikh"], "%Y-%m-%d %H:%M:%S").date()
            if ts >= start:
                total += float(r.get("Jumlah (RM)", 0))
        except Exception:
            continue

    return label, total

# ──────────────────────────────────────────────────────────────────────────────
# Fungsi hantar laporan kepada setiap pengguna
# ──────────────────────────────────────────────────────────────────────────────
def send_reports():
    users = get_all_users()
    for user in users:
        name = user["Nama"]
        chat_id = user["ChatID"]
        records = get_user_expenses(chat_id)

        # Ucapan mesra pembuka
        greeting = (
            f"Hai {name}!\n\n"
            "Ini laporan perbelanjaan daripada *LaporanBelanjaBot*.\n"
            "Semoga membantu anda urus kewangan dengan lebih cekap.\n\n"
        )
        try:
            bot.send_message(chat_id=chat_id, text=greeting, parse_mode="Markdown")
            for period in ("daily", "weekly", "monthly"):
                label, total = calculate_summary(records, period)
                message = f"📊 Perbelanjaan {label}:\nJumlah: RM{total:.2f}"
                bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logging.error(f"Gagal menghantar laporan ke {chat_id}: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Main entry point (dipanggil oleh cron-job atau scheduler)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.info("LaporanBelanjaBot: Mulakan penghantaran laporan kepada semua pengguna...")
    send_reports()
