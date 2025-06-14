# utils.py

import re
from datetime import datetime

def extract_expense_details(text: str):
    """
    Contoh input:
    "nasi lemak rm5.00" → {item: nasi lemak, amount: 5.00}
    """
    pattern = r"(.*?)(?:rm|RM|RM\s*)(\d+(?:\.\d{1,2})?)"
    match = re.search(pattern, text)
    if not match:
        return None
    
    item = match.group(1).strip().capitalize()
    amount = float(match.group(2))

    now = datetime.now()
    return {
        "item": item,
        "amount": amount,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
    }
