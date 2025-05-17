import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
import asyncio

# Logging
logging.basicConfig(level=logging.INFO)

# Get environment variables
BOT_TOKEN = os.environ.get("BOT2_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

if not BOT_TOKEN:
    raise Exception("Sila setkan environment variable: BOT2_TOKEN")

# Flask app
flask_app = Flask(__name__)

# Telegram application
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Welcome message
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selamat datang ke LaporanBelanjaBot! Gunakan /mingguan atau /bulanan untuk terima laporan.")

# Register command handlers
telegram_app.add_handler(CommandHandler("start", start))
# Tambah handler lain: /mingguan, /bulanan dsb

# Webhook endpoint
@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return "OK"

# Root route for testing
@flask_app.route("/", methods=["GET"])
def index():
    return "Bot 2 LaporanBelanja sedang berjalan."

# Start Flask
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
