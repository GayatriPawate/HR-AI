import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        if len(text.strip()) < 100:
            text = _ocr_pdf(file_bytes)
        return text
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


def _ocr_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        import pytesseract

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = ""
            for page in pdf.pages:
                img = page.to_image(resolution=300).original
                text += pytesseract.image_to_string(img)
        return text
    except Exception as e:
        return f"[OCR failed: {e}]"
