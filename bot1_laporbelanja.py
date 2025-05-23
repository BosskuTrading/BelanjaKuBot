
import os
import logging
import re
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from dotenv import load_dotenv
from sheets_utils import save_expense_to_sheet

load_dotenv()
TOKEN = os.getenv("BOT1_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8443"))

logging.basicConfig(level=logging.INFO)

CHOOSING_MODE, TYPING_EXPENSE = range(2)

def parse_expense_text(text):
    try:
        text = text.strip()
        match = re.search(r"(rm|RM)\s?(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE)
        if not match:
            return None

        amount = match.group(2)
        rm_start = match.start()
        rm_end = match.end()

        before = text[:rm_start].strip()
        after = text[rm_end:].strip()

        before_words = before.split()
        after_words = after.split()

        if not before_words and not after_words:
            return None

        if len(before_words) >= len(after_words):
            item = before.strip().title()
            location = after.strip().title()
        else:
            item = after.strip().title()
            location = before.strip().title()

        if not item or not amount:
            return None

        return {
            "item": item,
            "location": location if location else "-",
            "amount": amount
        }
    except Exception as e:
        print(f"[Parse Error]: {e}")
        return None

def get_now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

WELCOME_MSG = (
    "👋 Hai! Saya *LaporBelanjaBot*, pembantu rekod belanja anda.\n\n"
    "Sila taip maklumat belanja dalam format berikut:\n"
    "▫️ `RM10 Nasi lemak kedai Ali`\n"
    "▫️ `Teh tarik RM2 gerai bawah flat`\n"
    "▫️ `Sabun Dobi RM12`\n\n"
    "*Wajib ada jumlah RM dan barang dibeli.*\n"
    "Kedai/Tempat adalah pilihan.\n\n"
    "📝 *Bot ini hanya digunakan untuk merekod belanja anda.*\n"
    "📊 Untuk melihat laporan harian, mingguan dan bulanan anda:\n"
    "👉 Sila buka dan langgan bot khas laporan:\n"
    "➡️ @LaporanBelanjaBot\n\n"
    "Taip /cancel untuk berhenti bila-bila masa."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, parse_mode="Markdown")
    return TYPING_EXPENSE

async def received_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        return await cancel(update, context)

    user = update.effective_user
    chat_id = update.effective_chat.id
    data = parse_expense_text(text)

    if not data:
        await update.message.reply_text(
            "⚠️ Format tidak lengkap. Mesti ada *jumlah RM* dan *barang dibeli* seperti:\n"
            "`RM5 nasi lemak kedai Ali` atau `sabun RM2 kedai mamak`.",
            parse_mode="Markdown"
        )
        return TYPING_EXPENSE

    data.update({
        "timestamp": get_now_string(),
        "from": user.full_name,
        "chat_id": chat_id
    })

    try:
        save_expense_to_sheet(data)
        item = data.get("item", "-")
        location = data.get("location", "-")
        amount = data.get("amount", "-")
        reply_msg = f"✅ Disimpan!\n🍽 {item}\n📍 {location}\n💸 RM{amount}\n\nNak rekod belanja lain?"
        await update.message.reply_text(reply_msg)
    except Exception as e:
        await update.message.reply_text("❌ Gagal simpan ke Google Sheets. Sila cuba lagi nanti.")
        print(f"[Save Error]: {e}")

    return TYPING_EXPENSE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Sesi dibatalkan. Taip /start untuk mula semula.")
    return ConversationHandler.END

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot sedang ONLINE dan sedia membantu.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TYPING_EXPENSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("status", status))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"/{TOKEN}",
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
