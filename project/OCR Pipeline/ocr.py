import pytesseract
from pdf2image import convert_from_path
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Convert to grayscale — improves OCR accuracy on color scans and
    photos by removing color noise Tesseract doesn't need.
    """
    return image.convert("L")


def ocr_image(image_path: str) -> str:
    """Run OCR on a single image file (jpg, png, tiff, bmp, etc.)."""
    image = Image.open(image_path)
    image = preprocess_image(image)
    return pytesseract.image_to_string(image)


def ocr_pdf(pdf_path: str, dpi: int = 300) -> str:
    """
    Convert each PDF page into an image, then OCR it page by page.
    dpi=300 is the standard floor for OCR accuracy — below ~200-250 DPI,
    small text becomes ambiguous at the pixel level and error rates climb.
    """
    pages = convert_from_path(
        pdf_path,
        dpi=dpi,
        poppler_path=r"C:\poppler\Release-26.02.0-0\poppler-26.02.0\Library\bin"
    )

    text_per_page = []
    for i, page in enumerate(pages):
        page = preprocess_image(page)
        page_text = pytesseract.image_to_string(page)
        # Label each page so the chunk's origin stays traceable later
        text_per_page.append(f"[Page {i + 1}]\n{page_text}")

    return "\n\n".join(text_per_page)