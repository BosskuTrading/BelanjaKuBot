# requirements.txt
python-telegram-bot==20.3
Flask==2.3.2
gspread==5.7.2
google-auth==2.21.0

---

# README.md

# 📦 Telegram Expense Tracker Bot System (Professional Version)

This project consists of **two Telegram bots**:

- `LaporBelanjaBot` (Bot 1): Receives text and photo receipts, saves data to Google Sheets
- `LaporanBelanjaBot` (Bot 2): Sends weekly/monthly reports based on user’s expense history

### 🔧 Requirements

- Python 3.10+
- Telegram Bot Token for each bot
- Google Service Account & Google Sheet
- Render.com or any platform to deploy (supports Flask + Webhook)

### 📁 Environment Variables

Set the following env vars for each bot service on Render:

```env
BOT1_TOKEN=<Telegram Token for LaporBelanjaBot>
BOT2_TOKEN=<Telegram Token for LaporanBelanjaBot>
SHEET_ID=<Google Sheet ID>
GOOGLE_CREDENTIALS_BASE64=<Base64 encoded content of credentials.json>
```

To generate `GOOGLE_CREDENTIALS_BASE64`:
```bash
base64 credentials.json > encoded.txt
```

Then copy contents into environment variable.

### 📤 Deployment Steps on Render

1. Create GitHub repo, push code
2. Create **two web services** on Render:
   - `laporbelanja-bot`
   - `laporanbelanja-bot`
3. Set correct environment variables for each
4. Set build command (if needed): `pip install -r requirements.txt`
5. Set start command:
   - For Bot 1: `python bot1_laporbelanja.py`
   - For Bot 2: `python bot2_laporanbelanja.py`
6. After deployed, manually call Telegram API to set webhook:

```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
  -d "url=https://<your-render-url>/<BOT_TOKEN>"
```

---

### 📌 Bot Usage

#### Bot 1 (`LaporBelanjaBot`)
- `/start`: Show welcome instructions
- Send text: e.g. `nasi ayam 10.50` → bot saves to sheet
- Send photo: upload receipt → bot saves image

#### Bot 2 (`LaporanBelanjaBot`)
- `/start`: Show available commands
- `/mingguan`: Show total spend in last 7 days
- `/bulanan`: Show total spend in last 30 days

---

✅ Ready for professional usage.
Let me know if you want Google Sheet sample template!
