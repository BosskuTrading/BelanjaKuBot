import os
import logging
import re
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from dotenv import load_dotenv
from sheets_utils import save_expense_to_sheet
from ocr_utils import extract_text_from_image

# ── Konfigurasi token dan webhook ─────────────
load_dotenv()
TOKEN = os.getenv("BOT1_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8443"))

logging.basicConfig(level=logging.INFO)

# ── Status perbualan ─────────────
CHOOSING_MODE, TYPING_EXPENSE, WAITING_RECEIPT = range(3)

# ── Tetapan papan kekunci ────────
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

# ── Fungsi bantu ──────────────────
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
        print(f"[Parse Error]: {e}")
        return None

def get_now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Mesej permulaan ───────────────
WELCOME_MSG = (
    "👋 Hai! Saya *LaporBelanjaBot*, pembantu rekod belanja anda.\n\n"
    "Anda boleh:\n"
    "📌 Taip sendiri — `RM5 nasi lemak warung ali`\n"
    "📷 Hantar gambar resit — saya akan cuba baca & simpan\n\n"
    "Taip /cancel untuk berhenti bila-bila masa.\n"
    "Jom mula, pilih cara di bawah:"
)

# ── Fungsi bot ────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, reply_markup=main_menu, parse_mode="Markdown")
    return CHOOSING_MODE

async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Taip" in text:
        await update.message.reply_text("📝 Sila taip belanja anda. Contoh:\n`RM3.50 Teh Tarik Kedai Ali`", parse_mode="Markdown")
        return TYPING_EXPENSE
    elif "Gambar" in text or "OCR" in text:
        await update.message.reply_text("📷 Sila hantar gambar resit anda.")
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
            "⚠️ Format tak lengkap atau tiada jumlah dengan 'RM'.\n\n"
            "*Contoh yang betul:*\n"
            "▫️ `RM5.20 Nasi Lemak Warung Haji`\n"
            "▫️ `RM12 Sabun Dobi Giant`\n"
            "▫️ `RM3.50 Teh O Ais gerai depan rumah`\n\n"
            "Sila cuba semula ikut format di atas.",
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
        f"✅ Disimpan!\n🍽 {data['item']}\n📍 {data['location']}\n💸 RM{data['amount']}\n\n"
        "Nak rekod belanja lain?",
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
            "😓 Tak dapat baca resit ni dengan jelas.\n"
            "Nak cuba lagi atau taip sendiri?",
            reply_markup=retry_menu
        )
        return CHOOSING_MODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Sesi dibatalkan. Taip /start untuk mula semula.")
    return ConversationHandler.END

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot sedang ONLINE dan sedia membantu.")

# ── Main ──────────────────────────
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
