import re
from datetime import datetime

def parse_expense_text(text):
    """
    Menyokong input gaya bebas seperti:
    'RM5.00 teh ais warung ahmad'
    'beli di Mydin sabun RM8.50'
    'nasi lemak RM6.20 kafe Kak Yah'
    """

    try:
        match = re.search(r"RM\s?(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE)
        if not match:
            return None

        amount = match.group(1)
        # Pisahkan kepada kiri dan kanan jumlah
        parts = text.replace("RM", "").split(match.group(1))
        before = parts[0].strip()
        after = parts[1].strip() if len(parts) > 1 else ""

        # Heuristik: kiri = barang, kanan = lokasi
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
    """
    Dapatkan waktu semasa sebagai string standard.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
