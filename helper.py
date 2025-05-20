import re
from datetime import datetime

def get_now_string():
    """Dapatkan tarikh dan masa semasa dalam format ISO."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def parse_expense_text(text):
    """
    Cuba kenalpasti input teks belanja daripada pengguna.
    Format yang disokong (tidak sensitif huruf besar):
    Contoh: 'Nasi ayam, Warung Kak Nah, RM10.50'
    """
    try:
        # Pecah ikut koma
        parts = [p.strip() for p in text.split(',')]
        if len(parts) < 3:
            return None

        item, location, price_raw = parts[0], parts[1], parts[2]

        # Cari nilai RM
        match = re.search(r'RM?\s?([\d.]+)', price_raw.upper())
        if not match:
            return None

        price = float(match.group(1))

        return {
            'item': item,
            'location': location,
            'amount': price,
        }
    except Exception:
        return None
