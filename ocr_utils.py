import pytesseract
from PIL import Image

# (Optional) Set path if Tesseract is not in PATH
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_image(image_path):
    """
    Guna Tesseract OCR untuk baca teks daripada gambar resit.
    Input: image_path (str)
    Output: text (str)
    """
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""
