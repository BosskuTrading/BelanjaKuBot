import os
import logging
import threading
from flask import Flask
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sheets_utils import get_all_users, get_user_expenses
from apscheduler.schedulers.background import BackgroundScheduler

# ─── Muat .env ──────────────────────
load_dotenv()
TOKEN       = os.getenv("BOT2_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT        = int(os.getenv("PORT", "8443"))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

# ─── Flask App untuk Render detect port ─────
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "LaporanBelanjaBot aktif."

# ─── Fungsi laporan ─────────────────────────
def kira(records, period):
    total = 0.0
    now = datetime.now()

    if period == "daily":
        start, label = now.date(), "Hari Ini"
    elif period == "weekly":
        start, label = (now - timedelta(days=7)).date(), "Minggu Ini"
    else:
        start, label = now.replace(day=1).date(), "Bulan Ini"

    for r in records:
        try:
            t = datetime.strptime(r["Tarikh"], "%Y-%m-%d %H:%M:%S").date()
            if t >= start:
                total += float(r.get("Jumlah (RM)", 0))
        except:
            continue

    return label, total

def hantar_laporan():
    logging.info("LaporanBelanjaBot: Mulakan penghantaran laporan kepada semua pengguna...")
    users = get_all_users()
    for u in users:
        nama, cid = u["Nama"], u["ChatID"]
        data = get_user_expenses(cid)

        salam = (
            f"Hai {nama}!\n\n"
            "Ini laporan dari *LaporanBelanjaBot*.\n"
            "Semoga membantu anda urus kewangan dengan lebih bijak."
        )
        try:
            bot.send_message(chat_id=cid, text=salam, parse_mode="Markdown")
            for period in ("daily", "weekly", "monthly"):
                label, total = kira(data, period)
                msg = f"📊 Perbelanjaan {label}:\nJumlah: RM{total:.2f}"
                bot.send_message(chat_id=cid, text=msg)
        except Exception as e:
            logging.error(f"Gagal hantar ke {cid}: {e}")

# ─── Run Flask secara selari ────────────────
def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ─── Main PTB Bot + Scheduler ───────────────
def main():
    # Mula Flask dalam thread berasingan
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Setup scheduler harian
    scheduler = BackgroundScheduler()
    scheduler.add_job(hantar_laporan, 'cron', hour=8, minute=0)
    scheduler.start()

    # Placeholder app untuk webhook compatibility (jika mahu)
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: None))
    app.run_polling()  # Guna polling untuk kekalkan struktur

if __name__ == "__main__":
    main()
