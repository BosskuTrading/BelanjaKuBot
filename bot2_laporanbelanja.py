import os
import logging
import threading
from flask import Flask
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sheets_utils import get_all_users, get_user_expenses
from apscheduler.schedulers.background import BackgroundScheduler

# ─── Muat .env ──────────────────────
load_dotenv()
TOKEN       = os.getenv("BOT2_TOKEN")
PORT        = int(os.getenv("PORT", "10000"))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

# ─── Flask App ──────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "LaporanBelanjaBot sedang berjalan."

# ─── Kirakan jumlah belanja ─────────
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

# ─── Hantar laporan ke semua pengguna ──────────
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

# ─── Flask runner ──────────────────────────────
def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ─── Placeholder untuk command start ───────────
async def kosong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bot sedang aktif. Tiada fungsi khas di sini.")

# ─── Main ──────────────────────────────────────
def main():
    # Mula Flask di thread lain
    threading.Thread(target=run_flask).start()

    # Jadual laporan harian
    scheduler = BackgroundScheduler()
    scheduler.add_job(hantar_laporan, 'cron', hour=8, minute=0)
    scheduler.start()

    # Run bot polling
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", kosong))
    app.run_polling()

if __name__ == "__main__":
    main()
