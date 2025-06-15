import os
from flask import Request, jsonify, request
from telegram import Bot, Update
from telegram.ext import (
    CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
)
from telegram.ext import ApplicationBuilder
import datetime
import json
import base64
import gspread

TOKEN_BOT1 = os.getenv("TOKEN_BOT1")
SHEET_ID = os.getenv("SHEET_ID")

# ============ Google Sheet Client ============
def get_gspread_client():
    credentials_b64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    credentials_json = base64.b64decode(credentials_b64).decode("utf-8")
    credentials_dict = json.loads(credentials_json)
    return gspread.service_account_from_dict(credentials_dict)

def save_expense_to_sheet(chat_id, lokasi, amount, note):
    gc = get_gspread_client()
    sheet = gc.open_by_key(SHEET_ID)
    worksheet = sheet.sheet1
    now = datetime.datetime.now()
    row = [str(chat_id), now.strftime('%Y-%m-%d'), now.strftime('%H:%M'), lokasi, note, amount]
    worksheet.append_row(row)

# ============ Bot Handlers ============
# Bot branding
BOT_SIGNATURE = "\n\n_Bot ini dibawakan oleh Fadirul Ezwan_"

# States
ASK_LOKASI, ASK_NOTA, ASK_GAMBAR = range(3)
user_data = {}

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 Hai! Hantar perbelanjaan anda dalam format:\n"
        "`nasi ayam rm10.50` atau `buku rm15`\n\n"
        "Atau terus upload gambar resit.\n\n"
        "Taip /cancel untuk batalkan.\n"
        + BOT_SIGNATURE,
        parse_mode="Markdown"
    )

async def status(update: Update, context: CallbackContext):
    await update.message.reply_text("✅ Bot sedang aktif dan bersedia menerima maklumat belanja anda." + BOT_SIGNATURE)

async def cancel(update: Update, context: CallbackContext):
    user_data.pop(update.message.chat_id, None)
    await update.message.reply_text("❌ Transaksi dibatalkan." + BOT_SIGNATURE)

# Bila pengguna hantar teks seperti "nasi ayam rm10.50"
async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    chat_id = update.message.chat_id

    if "rm" not in text:
        await update.message.reply_text("Saya tak pasti jumlah belanja. Sila guna format seperti `nasi lemak rm5.00`")
        return

    try:
        amount_str = text.split("rm")[-1].strip()
        amount = float(amount_str)
        note = text.split("rm")[0].strip().title()
    except:
        await update.message.reply_text("Saya tak faham jumlah tu. Sila tulis contohnya `nasi ayam rm10.50`")
        return

    user_data[chat_id] = {"amount": amount, "note": note}
    await update.message.reply_text("📍 Sila nyatakan lokasi pembelian ini:")
    return ASK_LOKASI

async def ask_lokasi(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    lokasi = update.message.text
    user_data[chat_id]["lokasi"] = lokasi
    await update.message.reply_text("📝 Ada nota tambahan atau mahu terus simpan? (Boleh taip 'tiada')")
    return ASK_NOTA

async def ask_nota(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    nota = update.message.text
    if nota.lower() != "tiada":
        user_data[chat_id]["note"] += f" - {nota}"
    await update.message.reply_text("📷 Ada gambar resit? Sila upload sekarang atau taip 'tiada'")
    return ASK_GAMBAR

async def ask_gambar(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if update.message.text and update.message.text.lower() == "tiada":
        return await simpan_data(update, context)

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        user_data[chat_id]["photo_id"] = file_id
        await update.message.reply_text("✅ Gambar diterima.")
        return await simpan_data(update, context)
    else:
        await update.message.reply_text("Sila upload gambar atau taip 'tiada'.")
        return ASK_GAMBAR

async def simpan_data(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    data = user_data.get(chat_id)
    if not data:
        await update.message.reply_text("Ralat: Tiada data untuk disimpan.")
        return ConversationHandler.END

    save_expense_to_sheet(chat_id, data["lokasi"], data["amount"], data["note"])
    await update.message.reply_text("✅ Belanja berjaya disimpan!" + BOT_SIGNATURE)
    user_data.pop(chat_id, None)
    return ConversationHandler.END

# Bila mesej tak difahami
async def fallback(update: Update, context: CallbackContext):
    await update.message.reply_text("❓ Maaf, saya tak faham mesej anda. Sila cuba semula atau taip /start")

# ============ Flask Webhook Handler for Vercel ============
def handler(req: Request):
    application = ApplicationBuilder().token(TOKEN_BOT1).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
        states={
            ASK_LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_lokasi)],
            ASK_NOTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_nota)],
            ASK_GAMBAR: [
                MessageHandler(filters.PHOTO, ask_gambar),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gambar)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.ALL, fallback))

    update = Update.de_json(req.get_json(force=True), application.bot)
    application.process_update(update)

    return jsonify({"ok": True})
