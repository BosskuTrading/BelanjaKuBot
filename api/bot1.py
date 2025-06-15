import os
import re
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)
from sheets_utils import save_expense

TOKEN = os.getenv("TOKEN_BOT1")
app = Flask(__name__)

# --- States untuk conversation ---
(
    WAITING_TEXT,
    WAITING_LOKASI,
    WAITING_ITEM_LAIN,
    WAITING_GAMBAR,
) = range(4)

# --- Inisialisasi Telegram Bot Application ---
telegram_app = Application.builder().token(TOKEN).build()

# --- Command /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hai! Saya bot pembantu belanja harian anda.\n"
        "Hantar maklumat belanja seperti:\n"
        "`nasi ayam rm10.50`\n\n"
        "Atau upload gambar resit.\n\n"
        "_Bot ini dibawakan oleh Fadirul Ezwan._",
        parse_mode='Markdown'
    )
    return WAITING_TEXT

# --- Command /status ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot sedang aktif dan bersedia!")

# --- Command /cancel ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Proses dibatalkan. Anda boleh mula semula bila-bila masa.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Terima text contohnya 'nasi ayam rm12.50' ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    match = re.match(r"(.+)\s+rm([0-9.]+)", message.lower())
    if not match:
        await update.message.reply_text("⚠️ Saya tak faham format tu. Sila taip contoh seperti: `nasi ayam rm10.50`", parse_mode='Markdown')
        return WAITING_TEXT

    item = match.group(1).strip().title()
    jumlah = match.group(2).strip()

    context.user_data['item'] = item
    context.user_data['jumlah'] = jumlah

    await update.message.reply_text("📍 Di mana anda beli makanan ini?")
    return WAITING_LOKASI

async def handle_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lokasi = update.message.text.strip()
    context.user_data['lokasi'] = lokasi

    await update.message.reply_text("🛍️ Ada item lain dibeli sekali? (Taip `tiada` jika tiada)")
    return WAITING_ITEM_LAIN

async def handle_item_lain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nota = update.message.text.strip()
    context.user_data['nota'] = nota if nota.lower() != 'tiada' else ""

    await update.message.reply_text("📸 Ada gambar resit? Sila upload. Jika tiada, taip `skip`.")
    return WAITING_GAMBAR

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.photo[-1].get_file()
    image_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"

    context.user_data['image_url'] = image_url
    await save_and_confirm(update, context)
    return ConversationHandler.END

async def skip_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['image_url'] = ""
    await save_and_confirm(update, context)
    return ConversationHandler.END

async def save_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    data = {
        "tarikh": None,
        "masa": None,
        "lokasi": context.user_data.get('lokasi', ''),
        "kedai": context.user_data.get('lokasi', ''),
        "item": context.user_data.get('item', ''),
        "jumlah_item": "",  # boleh ditambah secara automatik jika mahu
        "jumlah": context.user_data.get('jumlah', ''),
        "nota": context.user_data.get('nota', ''),
        "image_url": context.user_data.get('image_url', '')
    }
    try:
        save_expense(user_id, data)
        await update.message.reply_text("✅ Maklumat belanja berjaya disimpan!\nTerima kasih.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Gagal simpan: {e}")

# --- fallback bila bot tak faham ---
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("😕 Maaf, saya tak faham. Cuba taip format: `nasi ayam rm10.50`", parse_mode='Markdown')
    return WAITING_TEXT

# --- Handler Conversation ---
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        WAITING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
        WAITING_LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lokasi)],
        WAITING_ITEM_LAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_item_lain)],
        WAITING_GAMBAR: [
            MessageHandler(filters.PHOTO, handle_image),
            MessageHandler(filters.TEXT & filters.Regex("^(skip|SKIP|Skip)$"), skip_image)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        MessageHandler(filters.COMMAND, fallback),
        MessageHandler(filters.ALL, fallback)
    ],
    allow_reentry=True
)

telegram_app.add_handler(conv_handler)
telegram_app.add_handler(CommandHandler("status", status))
telegram_app.add_handler(CommandHandler("cancel", cancel))

# --- Flask route untuk webhook ---
@app.route("/bot1", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        telegram_app.update_queue.put(update)
    return "ok"
