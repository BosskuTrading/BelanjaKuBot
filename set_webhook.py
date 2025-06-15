import os
import requests

DOMAIN = "https://belanjakubot.vercel.app"

BOT1_TOKEN = os.getenv("TOKEN_BOT1")
BOT2_TOKEN = os.getenv("TOKEN_BOT2")

def set_webhook(bot_token, path):
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    webhook_url = f"{DOMAIN}{path}"
    response = requests.post(url, json={"url": webhook_url})
    return response.status_code, response.json()

if __name__ == "__main__":
    status1, resp1 = set_webhook(BOT1_TOKEN, "/bot1")
    print("BOT1 Webhook:", status1, resp1)

    status2, resp2 = set_webhook(BOT2_TOKEN, "/bot2")
    print("BOT2 Webhook:", status2, resp2)
