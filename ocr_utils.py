import easyocr

# Inisialisasi hanya sekali
reader = easyocr.Reader(['en'])

def extract_text_from_image(image_path):
    """
    Guna EasyOCR untuk ekstrak teks dari imej.
    Jika gagal, pulang mesej fallback.
    """
    try:
        result = reader.readtext(image_path, detail=0)
        text = " ".join(result).strip()

        if text:
            print(f"✅ OCR berjaya [{image_path}]: {text}")
            return text
        else:
            print(f"⚠️ OCR tidak jumpa teks dalam {image_path}")
            return "[Resit dihantar tetapi tiada teks berjaya dikenalpasti.]"

    except Exception as e:
        print(f"❌ OCR Error di {image_path}: {e}")
        return "[Ralat semasa baca gambar resit. Sila cuba taip secara manual.]"
