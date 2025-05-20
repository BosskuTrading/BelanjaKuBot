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
from datetime import datetime
import re

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

retry_menu = ReplyKeyboardMarkup(
    [[KeyboardButton("📷 Cuba Semula OCR")],
     [KeyboardButton("✍️ Taip Maklumat Belanja")]],
    resize_keyboard=True, one_time_keyboard=True
)

def parse_expense_text(text):
    try:
        match = re.search(r"RM\s?(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE)
        if not match:
            return None
        amount = match.group(1)
        parts = text.replace("RM", "").split(match.group(1))
        before = parts[0].strip()
        after = parts[1].strip() if len(parts) > 1 else ""
        item = before or "Barang"
        location = after or "Tempat"
        return {
            "item": item.title(),
            "location": location.title(),
            "amount": amount
        }
    except Exception as e:
        print(f"Parse Error: {e}")
        return None

def get_now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

WELCOME_MSG = (
    "👋 Hai! Saya *LaporBelanjaBot*, pembantu belanja harian anda.\n\n"
    "Anda boleh:\n"
    "📌 *Taip belanja* — tak kisah ikut susunan mana pun!\n"
    "📷 *Hantar gambar resit* — saya cuba baca & simpan\n\n"
    "Taip /cancel untuk berhenti, /status untuk semak bot aktif."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, reply_markup=main_menu, parse_mode="Markdown")
    return CHOOSING_MODE

async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Taip" in text:
        await update.message.reply_text("📝 Sila taip belanja anda. Contoh:\n`RM5.20 Teh Ais Warung Haji`", parse_mode="Markdown")
        return TYPING_EXPENSE
    elif "Gambar" in text or "OCR" in text:
        await update.message.reply_text("📷 Sila hantar gambar resit anda sekarang.")
        return WAITING_RECEIPT
    else:
        await update.message.reply_text("❓ Sila pilih dari menu.", reply_markup=main_menu)
        return CHOOSING_MODE

async def received_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        return await cancel(update, context)

    user = update.effective_user
    chat_id = update.effective_chat.id
    data = parse_expense_text(text)

    if not data:
        await update.message.reply_text(
            "😅 Saya tak pasti maklumat tu lengkap...\n"
            "Cuba tulis contohnya: `RM8 Nasi Lemak Kafe Aisyah`",
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
        f"✅ Disimpan!\n🍽 {data['item']}\n📍 {data['location']}\n💸 RM{data['amount']}",
        reply_markup=main_menu
    )
    return CHOOSING_MODE

async def received_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    photo = update.message.photo[-1]
    file = await photo.get_file()
    os.makedirs("receipts", exist_ok=True)
    file_path = f"receipts/{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    text = extract_text_from_image(file_path)
    data = parse_expense_text(text)

    if data and data.get("item") and data.get("amount"):
        data.update({
            "timestamp": get_now_string(),
            "from": user.full_name,
            "chat_id": chat_id,
            "image_path": file_path
        })
        save_expense_to_sheet(data)

        await update.message.reply_text(
            f"✅ Resit dibaca & disimpan:\n\n🍽 {data['item']}\n📍 {data['location']}\n💸 {data['amount']}",
            reply_markup=main_menu
        )
        return CHOOSING_MODE
    else:
        await update.message.reply_text(
            "😓 Saya tak dapat camkan maklumat dari gambar ni.\n"
            "Nak cuba semula atau taip secara manual?",
            reply_markup=retry_menu
        )
        return CHOOSING_MODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Sesi dibatalkan. Taip /start untuk mula semula.")
    return ConversationHandler.END

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot sedang ONLINE dan bersedia membantu.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_mode)
            ],
            TYPING_EXPENSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_text)
            ],
            WAITING_RECEIPT: [
                MessageHandler(filters.PHOTO, received_photo)
            ],
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
