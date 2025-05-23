
import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
from sheets_utils import get_user_expenses

load_dotenv()
TOKEN = os.getenv("BOT2_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8443"))

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def fmt_date(d):
    return d.strftime("%d %B %Y")

def format_expenses(expenses):
    if not expenses:
        return "❌ Tiada belanja direkodkan dalam tempoh ini."
    lines = []
    total = 0
    for row in expenses:
        try:
            row_date = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            lines.append(f"🧾 {row[2]} | {row[3]} | RM{row[4]} | {fmt_date(row_date)}")
            total += float(row[4])
        except Exception as e:
            logging.warning(f"Skipping row due to error: {e}")
            continue
    return "\n".join(lines) + f"\n\n💰 Jumlah: RM{total:.2f}"

def filter_by_range(expenses, start_date, end_date):
    result = []
    for row in expenses:
        try:
            row_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").date()
            if start_date <= row_date <= end_date:
                result.append(row)
        except Exception as e:
            logging.warning(f"Date parsing error: {e}")
            continue
    return result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Harian", callback_data="harian")],
        [InlineKeyboardButton("🗓 Mingguan", callback_data="mingguan")],
        [InlineKeyboardButton("📆 Bulanan", callback_data="bulanan")],
        [InlineKeyboardButton("📋 Semua", callback_data="semua")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Hai! Saya *LaporanBelanjaBot*. Pilih laporan yang anda mahu lihat:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        logging.warning(f"answer_callback_query failed: {e}")
    chat_id = query.message.chat.id
    pilihan = query.data
    logging.info(f"Callback received: {pilihan} from chat_id {chat_id}")

    all_expenses = get_user_expenses(chat_id)
    today = datetime.today().date()

    if pilihan == "harian":
        start = end = today
        title = f"📅 Laporan Harian ({fmt_date(start)})"
    elif pilihan == "mingguan":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        title = f"🗓 Laporan Mingguan ({fmt_date(start)} – {fmt_date(end)})"
    elif pilihan == "bulanan":
        start = today.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
        title = f"📆 Laporan Bulanan ({fmt_date(start)} – {fmt_date(end)})"
    else:
        start = end = None
        title = "📋 Semua Laporan Belanja Anda"

    if start and end:
        filtered = filter_by_range(all_expenses, start, end)
    else:
        filtered = all_expenses

    result_text = format_expenses(filtered)
    if not result_text.strip():
        result_text = "❌ Tiada belanja direkodkan dalam tempoh ini."

    await query.edit_message_text(text=f"{title}\n\n{result_text}", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"/{TOKEN}",
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    logging.info("Bot2 LaporanBelanja is starting...")
    main()
