import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from dotenv import load_dotenv
from sheets_utils import save_expense_to_sheet
from ocr_utils import extract_text_from_image
from helper import parse_expense_text, get_now_string

# ─── Muat tetapan dari .env ───────────────────────
load_dotenv()
TOKEN       = os.getenv("BOT1_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")      # e.g. https://laporbelanjabot.onrender.com
PORT        = int(os.getenv("PORT", "8443"))

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT1_TOKEN dan WEBHOOK_URL mesti ditetapkan di Environment")

logging.basicConfig(level=logging.INFO)

# ─── Status perbualan ─────────────────────────────
CHOOSING_MODE, TYPING_EXPENSE, WAITING_RECEIPT = range(3)

# ─── Keyboard menu ────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Taip Maklumat Belanja")],
     [KeyboardButton("Hantar Gambar Resit")]],
    resize_keyboard=True, one_time_keyboard=True
)

# ─── Mesej sambutan & panduan ─────────────────────
WELCOME_MSG = (
    "👋 Hai! Saya *LaporBelanjaBot* – pembantu kewangan anda.\n\n"
    "*Apa saya boleh bantu?*\n"
    "1️⃣ Simpan belanja harian (taip atau resit)\n"
    "2️⃣ Rekod ke Google Sheets\n"
    "3️⃣ Laporan automatik via *LaporanBelanjaBot*\n\n"
    "*Cara guna:*\n"
    "• Tekan *Taip Maklumat Belanja*\n"
    "  Contoh: `Nasi Lemak, Warung Ali, RM5.00`\n"
    "• Tekan *Hantar Gambar Resit*\n"
    "  Ambil gambar resit & hantar di sini\n\n"
    "Taip `/cancel` untuk batal, `/status` untuk semak bot online."
)

# ─── Handler /start ───────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_MSG, reply_markup=keyboard, parse_mode="Markdown"
    )
    return CHOOSING_MODE

# ─── Handler pilihan menu ─────────────────────────
async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Taip Maklumat Belanja":
        await update.message.reply_text(
            "✅ Sila taip dalam format:\n"
            "`Item, Tempat, RM jumlah`\n"
            "Contoh: `Teh Tarik, Kafe Mamak, RM2.50`",
            parse_mode="Markdown"
        )
        return TYPING_EXPENSE
    if text == "Hantar Gambar Resit":
        await update.message.reply_text("✅ Sila hantar gambar resit anda sekarang.")
        return WAITING_RECEIPT
    await update.message.reply_text("❓ Sila pilih dari menu yang diberi.")
    return CHOOSING_MODE

# ─── Handler teks belanja ──────────────────────────
async def received_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        return await cancel(update, context)

    user    = update.effective_user
    chat_id = update.effective_chat.id
    data    = parse_expense_text(text)

    if not data:
        await update.message.reply_text(
            "⚠️ Format salah. Gunakan:\n"
            "`Item, Tempat, RM jumlah`\n"
            "Contoh: `Roti Canai, Restoran XYZ, RM1.80`",
            parse_mode="Markdown"
        )
        return TYPING_EXPENSE

    data.update({
        "timestamp": get_now_string(),
        "from":      user.full_name,
        "chat_id":   chat_id
    })
    save_expense_to_sheet(data)

    await update.message.reply_text(
        "✅ Terima kasih! Belanja anda telah direkod.\n"
        "Taip `/start` untuk rekod lain."
    )
    return ConversationHandler.END

# ─── Handler gambar resit ─────────────────────────
async def received_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    chat_id = update.effective_chat.id

    photo      = update.message.photo[-1]
    photo_file = await photo.get_file()
    os.makedirs("receipts", exist_ok=True)
    file_path  = f"receipts/{photo.file_id}.jpg"
    await photo_file.download_to_drive(file_path)

    text = extract_text_from_image(file_path)
    data = parse_expense_text(text) or {}
    data.update({
        "timestamp":  get_now_string(),
        "from":       user.full_name,
        "chat_id":    chat_id,
        "image_path": file_path
    })
    save_expense_to_sheet(data)

    await update.message.reply_text("✅ Gambar resit diterima dan disimpan.")
    return ConversationHandler.END

# ─── Handler /cancel ──────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operasi dibatalkan. Taip `/start` semula.")
    return ConversationHandler.END

# ─── Handler /status ──────────────────────────────
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ *LaporBelanjaBot* sedang *ONLINE* dan sedia membantu anda.",
        parse_mode="Markdown"
    )

# ─── Program utama ───────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MODE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_mode)],
            TYPING_EXPENSE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, received_text)],
            WAITING_RECEIPT:  [MessageHandler(filters.PHOTO, received_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("status", status))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"/bot1/{TOKEN}",
        webhook_url=f"{WEBHOOK_URL}/bot1/{TOKEN}"
    )

if __name__ == "__main__":
    main()
