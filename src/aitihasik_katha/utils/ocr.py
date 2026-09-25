import io
from functools import lru_cache

from google.cloud import vision


@lru_cache(maxsize=1)
def _get_client() -> vision.ImageAnnotatorClient:
    return vision.ImageAnnotatorClient()


def extract_text(image) -> str:
    """Extract text content from a PIL image using Vision OCR."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    content = buffer.getvalue()
    image_obj = vision.Image(content=content)

    response = _get_client().text_detection(image=image_obj)
    if response.full_text_annotation:
        return response.full_text_annotation.text
    return ""
