import gc
import os
import tempfile
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pdf2image import convert_from_path
from pypdf import PdfReader

from ..core.logging import get_logger
from ..storage.vector_store import get_store
from ..utils.ocr import extract_text
from ..utils.translation import translate_text_sync


logger = get_logger(__name__)


def load_pdf(doc_path: str, language: str = "en", batch_size: int = 50) -> list[Document]:
    """Convert PDF pages to text chunks with optional Nepali translation."""
    if not doc_path:
        return []

    reader = PdfReader(doc_path)
    total_pages = len(reader.pages)
    content_parts: list[str] = []

    for start_page in range(1, total_pages + 1, batch_size):
        end_page = min(start_page + batch_size - 1, total_pages)
        logger.info("Processing pages %s to %s of %s", start_page, end_page, total_pages)

        with tempfile.TemporaryDirectory() as path:
            images = convert_from_path(
                doc_path,
                first_page=start_page,
                last_page=end_page,
                output_folder=path,
            )

            for image in images:
                text = extract_text(image)
                if language == "ne":
                    text = translate_text_sync(text)
                content_parts.append(text)

                image = None
                gc.collect()

    metadata = {"source": doc_path}
    return [Document(metadata=metadata, page_content="\n".join(content_parts))]


def split_text(documents: list[Document]) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=300)
    return text_splitter.split_documents(documents)


def add_to_vector_store(chunks: list[Document], source: str) -> None:
    vector_store = get_store()
    if not vector_store.document_exists(source):
        vector_store.add_document(source, chunks)


def ingest_pdf(doc_path: str, language: str = "en") -> None:
    if get_store().document_exists(doc_path):
        logger.info("%s is already in store", doc_path)
        return

    logger.info("Adding %s to vector store", doc_path)
    data = load_pdf(doc_path, language)
    chunks = split_text(data)
    add_to_vector_store(chunks, doc_path)

    data = None
    chunks = None
    gc.collect()

    logger.info("Added %s to vector store", doc_path)


def ingest_directory(base_dir: str = "data/pdfs") -> None:
    en_dir = Path(base_dir) / "en"
    ne_dir = Path(base_dir) / "ne"

    if en_dir.exists():
        for file in os.listdir(en_dir):
            ingest_pdf(str(en_dir / file), language="en")

    if ne_dir.exists():
        for file in os.listdir(ne_dir):
            ingest_pdf(str(ne_dir / file), language="ne")
