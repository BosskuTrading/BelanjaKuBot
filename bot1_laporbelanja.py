# bot1_laporbelanja.py

import os
import base64
import json
import logging
from flask import Flask, request
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputFile
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from google_sheets_helper import append_expense_row
from utils import extract_expense_details

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States for ConversationHandler
AMOUNT, LOCATION, MORE_ITEMS, IMAGE = range(4)

# Telegram Bot Token
TOKEN = os.environ.get("TOKEN_BOT1")

# Flask app
app = Flask(__name__)
BOT_ROUTE = "/bot1"

# Load Google Service Account Credentials from base64
from google.oauth2 import service_account
import gspread

creds_json = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_BASE64"]).decode("utf-8")
creds_dict = json.loads(creds_json)
gc = gspread.service_account_from_dict(creds_dict)
SHEET_ID = os.environ["SHEET_ID"]
sheet = gc.open_by_key(SHEET_ID).sheet1


# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hai! Saya *Lapor Belanja Bot*.\n\n"
        "Hantar maklumat belanja anda seperti:\n"
        "`nasi lemak rm5.00`\n\n"
        "Atau hantar gambar resit 📷\n\n"
        "Perlu bantuan? Taip /cancel untuk batal.\n\n"
        "_Bot ini dibawakan oleh Fadirul Ezwan_ ❤️",
        parse_mode="Markdown"
    )
    return AMOUNT


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot sedang beroperasi dengan baik.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Input dibatalkan. Anda boleh mula semula bila-bila masa.")
    return ConversationHandler.END


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    details = extract_expense_details(user_input)
    if not details:
        await update.message.reply_text("😅 Maaf, saya tak faham format itu. Contoh: `nasi lemak rm5.00`", parse_mode="Markdown")
        return AMOUNT

    context.user_data["expense"] = details
    await update.message.reply_text("📍 Di mana anda beli ini?")
    return LOCATION


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["expense"]["location"] = update.message.text
    await update.message.reply_text("🛒 Ada barang lain dibeli sekali?")
    return MORE_ITEMS


async def handle_more_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    more = update.message.text
    context.user_data["expense"]["more_items"] = more
    await update.message.reply_text("📷 Kalau ada resit, boleh hantar gambar sekarang.")
    return IMAGE


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_url = file.file_path
    context.user_data["expense"]["image_url"] = file_url

    return await save_and_confirm(update, context)


async def save_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data["expense"]
    user_id = str(update.effective_user.id)

    # Append to Google Sheets
    row = [
        user_id,
        data.get("date", ""), 
        data.get("time", ""), 
        data.get("location", ""), 
        data.get("item", ""), 
        data.get("amount", ""), 
        data.get("more_items", ""), 
        data.get("image_url", "")
    ]
    append_expense_row(sheet, row)

    await update.message.reply_text("✅ Belanja anda telah direkodkan!\nTerima kasih 🙏")
    return ConversationHandler.END


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Maaf, saya tak faham arahan itu. Cuba taip contoh: `nasi ayam rm10.50`")

# --- Setup Telegram App ---

application = Application.builder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_location)],
        MORE_ITEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_more_items)],
        IMAGE: [
            MessageHandler(filters.PHOTO, handle_image),
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_and_confirm)
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        MessageHandler(filters.COMMAND, handle_unknown)
    ],
)

application.add_handler(conv_handler)
application.add_handler(CommandHandler("status", status))
application.add_handler(CommandHandler("cancel", cancel))
application.add_handler(MessageHandler(filters.TEXT, handle_unknown))


# --- Flask Webhook Integration ---

@app.route(BOT_ROUTE, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

@app.route("/", methods=["GET"])
def index():
    return "🤖 LaporBelanjaBot Webhook OK"
