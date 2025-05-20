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

load_dotenv()
TOKEN = os.getenv("TOKEN_BOT1")
logging.basicConfig(level=logging.INFO)

# Conversation states
CHOOSING_MODE, TYPING_EXPENSE, WAITING_RECEIPT = range(3)

keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Taip Maklumat Belanja")],
     [KeyboardButton("Hantar Gambar Resit")]],
    resize_keyboard=True, one_time_keyboard=True
)

WELCOME_MSG = (
    "Hai! Saya *LaporBelanjaBot*, pembantu kewangan peribadi anda. "
    "Bot ini dibawakan oleh *Fadirul Ezwan*.\n\n"
    "Dengan saya, anda boleh rekod perbelanjaan & gambar resit, dan saya akan simpan semuanya.\n"
    "Laporan perbelanjaan anda akan dihantar oleh *LaporanBelanjaBot* secara automatik.\n\n"
    "*Cara guna:*"
    "\n1. Tekan 'Taip Maklumat Belanja' dan masukkan contoh: `Nasi Lemak, Restoran Ali, RM8.00`"
    "\n2. Atau tekan 'Hantar Gambar Resit' untuk ambil gambar pembelian.\n\n"
    "Saya akan simpan semuanya di Google Sheet dan bantu anda buat laporan mingguan & bulanan.\n\n"
    "Sila pilih cara untuk mulakan:"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, reply_markup=keyboard, parse_mode="Markdown")
    return CHOOSING_MODE

async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Taip Maklumat Belanja":
        await update.message.reply_text("Sila taip maklumat belanja anda (contoh: Nasi Lemak, Restoran Ali, RM8.50)")
        return TYPING_EXPENSE

    elif text == "Hantar Gambar Resit":
        await update.message.reply_text("Sila hantar gambar resit anda sekarang.")
        return WAITING_RECEIPT

    else:
        await update.message.reply_text("Saya tak faham arahan ini. Sila pilih dari menu yang diberi.")
        return CHOOSING_MODE

async def received_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    chat_id = update.effective_chat.id

    if "/cancel" in text:
        return await cancel(update, context)

    data = parse_expense_text(text)
    if not data:
        await update.message.reply_text(
            "Maaf, saya tak faham. Sila taip dengan format:\n"
            "*Nama item, Lokasi, RM jumlah* (contoh: Teh Tarik, Kedai Ali, RM2.50)",
            parse_mode="Markdown"
        )
        return TYPING_EXPENSE

    data['timestamp'] = data.get('timestamp') or get_now_string()
    data['from'] = user.full_name
    data['chat_id'] = chat_id
    save_expense_to_sheet(data)

    await update.message.reply_text("Terima kasih! Maklumat belanja anda telah direkod.")
    return ConversationHandler.END

async def received_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    os.makedirs("receipts", exist_ok=True)
    file_path = f"receipts/{photo.file_id}.jpg"
    await photo_file.download_to_drive(file_path)

    text = extract_text_from_image(file_path)
    data = parse_expense_text(text)
    if data:
        data['timestamp'] = get_now_string()
        data['from'] = user.full_name
        data['chat_id'] = chat_id
        data['image_path'] = file_path
        save_expense_to_sheet(data)
        await update.message.reply_text("Resit berjaya dibaca dan direkod. Terima kasih!")
    else:
        await update.message.reply_text("Resit diterima, tapi saya tak dapat baca butirannya. Sila taip secara manual.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operasi dibatalkan. Taip /start untuk mula semula.")
    return ConversationHandler.END

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ *Bot ini (LaporBelanjaBot)* sedang ONLINE dan sedia membantu.\n\n"
        "Maklumat belanja anda akan direkod dan laporan akan dihantar oleh *LaporanBelanjaBot*.",
        parse_mode="Markdown"
    )

def main():
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
