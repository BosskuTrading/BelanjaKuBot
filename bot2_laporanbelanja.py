import os
import logging
import threading
from flask import Flask
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from sheets_utils import get_all_users, get_user_expenses

# ── Konfigurasi ────────────────────────
load_dotenv()
TOKEN = os.getenv("BOT2_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)

flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "LaporanBelanjaBot aktif."

# ── Pengiraan ──────────────────────────
def kira(records, period):
    total = 0.0
    now = datetime.now()

    if period == "daily":
        start = now.date()
        label = "Hari Ini"
    elif period == "weekly":
        start = (now - timedelta(days=7)).date()
        label = "Minggu Ini"
    else:
        start = now.replace(day=1).date()
        label = "Bulan Ini"

    for r in records:
        try:
            t = datetime.strptime(r["Tarikh"], "%Y-%m-%d %H:%M:%S").date()
            if t >= start:
                total += float(r.get("Jumlah (RM)", 0))
        except:
            continue

    return label, total

# ── Fungsi kirim mesej laporan ke pengguna ───────
def hantar_laporan():
    logging.info("Bot2: Hantar laporan automatik kepada semua pengguna...")
    users = get_all_users()
    for u in users:
        nama, cid = u["Nama"], u["ChatID"]
        data = get_user_expenses(cid)

        try:
            bot.send_message(chat_id=cid, text=f"Hai {nama}!\nBerikut laporan ringkas anda hari ini:")

            for period in ("daily", "weekly", "monthly"):
                label, total = kira(data, period)
                msg = f"📊 {label}:\nJumlah Belanja: *RM{total:.2f}*"
                bot.send_message(chat_id=cid, text=msg, parse_mode="Markdown")

        except Exception as e:
            logging.error(f"❌ Gagal hantar ke {cid}: {e}")

# ── Flask run ─────────────────────────────
def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ── Arahan manual dari pengguna ─────────────
async def laporan_manual(update: Update, context: ContextTypes.DEFAULT_TYPE, period):
    cid = update.effective_chat.id
    data = get_user_expenses(cid)

    label, total = kira(data, period)
    await update.message.reply_text(f"📊 {label}:\nJumlah Belanja: *RM{total:.2f}*", parse_mode="Markdown")

# ── Komando Khusus ─────────────────────────
async def laporan_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await laporan_manual(update, context, "daily")

async def laporan_mingguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await laporan_manual(update, context, "weekly")

async def laporan_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await laporan_manual(update, context, "monthly")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hai! Saya *LaporanBelanjaBot*.\n"
                                    "Gunakan arahan berikut untuk semak laporan:\n\n"
                                    "`/harian` – Laporan hari ini\n"
                                    "`/mingguan` – Minggu ini\n"
                                    "`/bulanan` – Bulan ini",
                                    parse_mode="Markdown")

# ── Main ───────────────────────────────────
def main():
    threading.Thread(target=run_flask).start()

    scheduler = BackgroundScheduler()
    scheduler.add_job(hantar_laporan, 'cron', hour=8, minute=0)
    scheduler.start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("harian", laporan_harian))
    app.add_handler(CommandHandler("mingguan", laporan_mingguan))
    app.add_handler(CommandHandler("bulanan", laporan_bulanan))

    app.run_polling()

if __name__ == "__main__":
    main()
