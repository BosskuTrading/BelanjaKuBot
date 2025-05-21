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

load_dotenv()
TOKEN = os.getenv("BOT1_TOKEN")

logging.basicConfig(level=logging.INFO)

CHOOSING_MODE, TYPING_EXPENSE = range(2)

main_menu = ReplyKeyboardMarkup(
    [[KeyboardButton("Taip Maklumat Belanja")]],
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
        print(f"[Ralat Format]: {e}")
        return None

def get_now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

WELCOME_MSG = (
    "👋 Hai! Saya *LaporBelanjaBot*, pembantu rekod belanja anda.\n\n"
    "📌 Sila taip belanja anda. Contoh:\n`RM5 Nasi lemak warung ali`\n\n"
    "Taip /cancel untuk berhenti bila-bila masa."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, reply_markup=main_menu, parse_mode="Markdown")
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
    app.run_polling()

if __name__ == "__main__":
    main()
