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

# Muat .env dan baca token
load_dotenv()
TOKEN = os.getenv("BOT1_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT1_TOKEN belum disetkan di environment!")

# Setup logging
logging.basicConfig(level=logging.INFO)

# Conversation states
CHOOSING_MODE, TYPING_EXPENSE, WAITING_RECEIPT = range(3)

# Keyboard menu pilihan
keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Taip Maklumat Belanja")],
     [KeyboardButton("Hantar Gambar Resit")]],
    resize_keyboard=True, one_time_keyboard=True
)

# Mesej sambutan dengan panduan langkah demi langkah
WELCOME_MSG = (
    "👋 Hai! Saya *LaporBelanjaBot*, pembantu kewangan anda.\n\n"
    "Jika ini kali pertama anda guna bot:\n"
    "1. Buka chat ini dan taip `/start`\n"
    "2. Anda akan nampak 2 butang:\n"
    "   • *Taip Maklumat Belanja* – untuk masukkan perbelanjaan manual\n"
    "   • *Hantar Gambar Resit* – untuk hantar gambar resit (bot baca teks automatik)\n\n"
    "Contoh guna *Taip Maklumat Belanja*:\n"
    "  `Nasi Lemak, Warung Kak Nah, RM8.50`\n\n"
    "Contoh guna *Hantar Gambar Resit*:\n"
    "  Ambil gambar resit dan tekan butang itu, kemudian hantar gambar.\n\n"
    "📌 Kalau tersilap taip, guna `/cancel` untuk mula semula.\n"
    "📌 Taip `/status` bila-bila masa untuk semak bot sedang *online*.\n\n"
    "Sila tekan satu butang di bawah untuk mula:"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /start – paparkan panduan dan menu pilihan."""
    await update.message.reply_text(
        WELCOME_MSG,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return CHOOSING_MODE

async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler apabila pengguna pilih modus input belanja."""
    text = update.message.text
    if text == "Taip Maklumat Belanja":
        await update.message.reply_text(
            "✅ Masukkan maklumat perbelanjaan anda seperti:\n"
            "`Nama item, Lokasi, RM jumlah`\n"
            "Contoh: `Teh Tarik, Kafe Mamak, RM2.50`\n\n"
            "Taip /cancel jika mahu batal.",
            parse_mode="Markdown"
        )
        return TYPING_EXPENSE

    if text == "Hantar Gambar Resit":
        await update.message.reply_text(
            "✅ Sila ambil gambar resit pembelian anda,\n"
            "kemudian hantar melalui chat ini.\n\n"
            "Taip /cancel jika mahu batal."
        )
        return WAITING_RECEIPT

    # Jika input lain
    await update.message.reply_text("❓ Sila pilih *Taip Maklumat Belanja* atau *Hantar Gambar Resit* saja.", parse_mode="Markdown")
    return CHOOSING_MODE

async def received_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler apabila pengguna taip teks belanja."""
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        return await cancel(update, context)

    user = update.effective_user
    chat_id = update.effective_chat.id
    data = parse_expense_text(text)

    if not data:
        # Jika format salah
        await update.message.reply_text(
            "⚠️ Format tak betul. Sila guna:\n"
            "`Nama item, Lokasi, RM jumlah`\n"
            "Contoh: `Roti Canai, Restoran XYZ, RM1.80`",
            parse_mode="Markdown"
        )
        return TYPING_EXPENSE

    # Lengkapkan data
    data.update({
        "timestamp": get_now_string(),
        "from": user.full_name,
        "chat_id": chat_id
    })
    save_expense_to_sheet(data)

    # Mesej pengesahan
    await update.message.reply_text(
        "🎉 Terima kasih! Rekod belanja anda telah disimpan.\n"
        "Untuk lapor belanja lain, taip /start semula."
    )
    return ConversationHandler.END

async def received_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler apabila pengguna hantar gambar resit."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    os.makedirs("receipts", exist_ok=True)
    file_path = f"receipts/{photo.file_id}.jpg"
    await photo_file.download_to_drive(file_path)

    text = extract_text_from_image(file_path)
    data = parse_expense_text(text) or {}
    data.update({
        "timestamp": get_now_string(),
        "from": user.full_name,
        "chat_id": chat_id,
        "image_path": file_path
    })
    save_expense_to_sheet(data)

    await update.message.reply_text(
        "✅ Gambar resit diterima dan rekod telah disimpan.\n"
        "Taip /start untuk lapor belanja lain."
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /cancel – batalkan sesi semasa."""
    await update.message.reply_text("❌ Operasi dibatalkan. Taip /start untuk mula semula.")
    return ConversationHandler.END

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /status – tunjukkan bot online."""
    await update.message.reply_text(
        "✅ *LaporBelanjaBot* sedang *ONLINE*.\n"
        "Gunakan menu atau taip /start untuk mula.\n"
        "Laporan automatik dihantar oleh *LaporanBelanjaBot*.",
        parse_mode="Markdown"
    )

def main():
    """Mulakan bot polling."""
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_mode)],
            TYPING_EXPENSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_text)],
            WAITING_RECEIPT: [MessageHandler(filters.PHOTO, received_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("status", status))
    app.run_polling()

if __name__ == "__main__":
    main()
