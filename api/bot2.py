import os
from flask import Request, Response, jsonify, request
from telegram import Bot
import datetime

from sheets_utils import get_user_expenses_summary

TOKEN_BOT2 = os.getenv("TOKEN_BOT2")
SHEET_ID = os.getenv("SHEET_ID")

bot = Bot(token=TOKEN_BOT2)

def send_daily_reports():
    users = get_user_expenses_summary(SHEET_ID)
    for user_id, summary in users.items():
        msg = (
            f"📊 *Laporan Harian Belanja*\n\n"
            f"Tarikh: {datetime.datetime.now().strftime('%d/%m/%Y')}\n"
            f"Jumlah Belanja Hari Ini: RM{summary.get('daily', 0):.2f}\n\n"
            "_Bot ini dibawakan oleh Fadirul Ezwan_"
        )
        bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")

def send_weekly_reports():
    users = get_user_expenses_summary(SHEET_ID)
    for user_id, summary in users.items():
        msg = (
            f"📈 *Laporan Mingguan Belanja*\n\n"
            f"Minggu: {datetime.datetime.now().isocalendar()[1]}\n"
            f"Jumlah Belanja Minggu Ini: RM{summary.get('weekly', 0):.2f}\n\n"
            "_Bot ini dibawakan oleh Fadirul Ezwan_"
        )
        bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")

def send_monthly_reports():
    users = get_user_expenses_summary(SHEET_ID)
    for user_id, summary in users.items():
        msg = (
            f"📅 *Laporan Bulanan Belanja*\n\n"
            f"Bulan: {datetime.datetime.now().strftime('%B %Y')}\n"
            f"Jumlah Belanja Bulan Ini: RM{summary.get('monthly', 0):.2f}\n\n"
            "_Bot ini dibawakan oleh Fadirul Ezwan_"
        )
        bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")

# ================================
# Main Vercel Handler
# ================================

def handler(req: Request) -> Response:
    report_type = req.args.get("type", "daily")
    today = datetime.datetime.now()

    if report_type == "daily":
        send_daily_reports()
    elif report_type == "weekly_or_monthly":
        send_weekly_reports()
        if today.day == 1:
            send_monthly_reports()

    return jsonify({"status": "ok", "report_type": report_type})
