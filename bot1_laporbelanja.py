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
TOKEN = os.getenv("BOT1_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8443"))

logging.basicConfig(level=logging.INFO)

CHOOSING_MODE, TYPING_EXPENSE, WAITING_RECEIPT = range(3)

main_menu = ReplyKeyboardMarkup(
    [[KeyboardButton("Taip Maklumat Belanja")],
     [KeyboardButton("Hantar Gambar Resit")]],
    resize_keyboard=True, one_time_keyboard=True
)

WELCOME_MSG = (
    "👋 Hai! Saya *LaporBelanjaBot*, pembantu belanja harian anda.\n\n"
    "Anda boleh:\n"
    "📌 *Taip belanja* (contoh: `Nasi Lemak, Warung Ali, RM5.00`)\n"
    "📷 *Hantar gambar resit* (saya baca & simpan)\n\n"
    "Taip /cancel untuk berhenti, /status untuk semak bot aktif."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, reply_markup=main_menu, parse_mode="Markdown")
    return CHOOSING_MODE

async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Taip Maklumat Belanja":
        await update.message.reply_text(
            "📝 Okey, sila taip perbelanjaan anda.\n"
            "Contoh: `Teh Tarik, Kedai Ali, RM2.50`",
            parse_mode="Markdown"
        )
        return TYPING_EXPENSE
    elif text == "Hantar Gambar Resit":
        await update.message.reply_text("📷 Sila hantar gambar resit anda.")
        return WAITING_RECEIPT
    else:
        await update.message.reply_text("❓ Sila pilih dari menu ya.", reply_markup=main_menu)
        return CHOOSING_MODE

async def received_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        return await cancel(update, context)

    user = update.effective_user
    chat_id = update.effective_chat.id
    data = parse_expense_text(text)

    if not data:
        # Cuba bantu auto-cadangkan jika user taip tanpa koma
        words = text.replace("RM", " RM").split()
        rm_index = next((i for i, w in enumerate(words) if w.startswith("RM")), -1)
        if rm_index >= 2:
            item = " ".join(words[:rm_index - 1])
            tempat = words[rm_index - 1]
            jumlah = words[rm_index]
            cadangan = f"{item}, {tempat}, {jumlah}"
            await update.message.reply_text(
                f"⚠️ Format nampak macam salah...\n\n"
                f"Adakah anda maksudkan:\n`{cadangan}`?\n\n"
                f"Cuba taip semula ikut format: `Item, Tempat, RM jumlah`\n"
                f"Contoh: `Roti Canai, Kafe ABC, RM3.00`",
                parse_mode="Markdown",
                reply_markup=main_menu
            )
        else:
            await update.message.reply_text(
                "😅 Saya tak dapat baca ayat tu...\n\n"
                "Sila guna format mudah:\n`Item, Tempat, RM jumlah`\n"
                "Contoh: `Kopi O, Gerai Makcik, RM1.50`",
                parse_mode="Markdown",
                reply_markup=main_menu
            )
        return TYPING_EXPENSE

    data.update({
        "timestamp": get_now_string(),
        "from": user.full_name,
        "chat_id": chat_id
    })
    save_expense_to_sheet(data)

    await update.message.reply_text(
        f"✅ Berjaya simpan!\n\n"
        f"🍽 {data['item']}\n📍 {data['location']}\n💸 {data['amount']}",
        reply_markup=main_menu
    )
    return ConversationHandler.END

async def received_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    photo = update.message.photo[-1]
    file = await photo.get_file()
    os.makedirs("receipts", exist_ok=True)
    file_path = f"receipts/{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    text = extract_text_from_image(file_path)
    data = parse_expense_text(text) or {}
    data.update({
        "timestamp": get_now_string(),
        "from": user.full_name,
        "chat_id": chat_id,
        "image_path": file_path
    })
    save_expense_to_sheet(data)

    await update.message.reply_text("✅ Gambar resit diterima dan telah direkod.", reply_markup=main_menu)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Sesi dibatalkan. Taip /start untuk mula semula.")
    return ConversationHandler.END

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot sedang ONLINE dan sedia membantu anda.")

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

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"/bot1/{TOKEN}",
        webhook_url=f"{WEBHOOK_URL}/bot1/{TOKEN}"
    )

if __name__ == "__main__":
    main()
