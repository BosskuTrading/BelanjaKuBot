
import os
import requests

TOKEN = os.getenv("BOT1_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

def set_webhook():
    full_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    data = {"url": f"{WEBHOOK_URL}/{TOKEN}"}
    response = requests.post(full_url, data=data)
    print("[Webhook Response]", response.status_code, response.text)

if __name__ == "__main__":
    print("[INFO] Setting Telegram Webhook...")
    set_webhook()
