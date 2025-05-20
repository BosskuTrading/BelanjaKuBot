import os
import logging
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sheets_utils import get_all_users, get_user_expenses
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

# ─── Muat tetapan dari .env ──────────────────────────────
load_dotenv()
TOKEN       = os.getenv("BOT2_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")      # e.g. https://laporanbelanjabot.onrender.com
PORT        = int(os.getenv("PORT", "8443"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT2_TOKEN dan WEBHOOK_URL mesti ditetapkan di Environment")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

# ─── Fungsi kira jumlah belanja ───────────────────────────
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

# ─── Fungsi hantar laporan ────────────────────────────────
def hantar_laporan():
    logging.info("LaporanBelanjaBot: Mulakan penghantaran laporan kepada semua pengguna...")
    users = get_all_users()
    for u in users:
        nama, cid = u["Nama"], u["ChatID"]
        data      = get_user_expenses(cid)

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
            logging.error(f"Gagal hantar laporan kepada {cid}: {e}")

# ─── Flask untuk Render Web Service kekal hidup ───────────
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "LaporanBelanjaBot sedang berjalan."

# ─── Program utama ────────────────────────────────────────
def main():
    # Jadual laporan harian (boleh ubah waktu)
    scheduler = BackgroundScheduler()
    scheduler.add_job(hantar_laporan, 'cron', hour=8, minute=0)
    scheduler.start()

    # Telegram Application
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: None))  # Placeholder command

    # Jalankan Webhook dan Flask
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"/bot2/{TOKEN}",
        webhook_url=f"{WEBHOOK_URL}/bot2/{TOKEN}",
        web_app=flask_app  # ← ini penting untuk elak timeout di Render
    )

if __name__ == "__main__":
    main()
