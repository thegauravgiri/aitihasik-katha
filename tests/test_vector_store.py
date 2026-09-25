import numpy as np
import pandas as pd
import pytest

from aitihasik_katha.storage import vector_store as vector_store_module
from aitihasik_katha.storage.vector_store import VectorStore


class _FakeSentenceTransformer:
    """Stands in for SentenceTransformer so tests don't download/load a real model."""

    _VECTORS = {
        "query about apples": [1.0, 0.0, 0.0],
        "query about oranges": [0.0, 1.0, 0.0],
        "totally unrelated": [0.0, 0.0, -1.0],
    }

    def __init__(self, model_name):
        self.model_name = model_name

    def encode(self, text):
        return np.array(self._VECTORS[text], dtype="float32")


def _write_store_files(tmp_path, ids, documents, metadatas, embedding_ids, embeddings):
    documents_path = tmp_path / "documents.json"
    embeddings_path = tmp_path / "embeddings.json"

    pd.DataFrame({"ids": ids, "documents": documents, "metadatas": metadatas}).to_json(
        documents_path, orient="records", lines=True
    )
    pd.DataFrame({"id": embedding_ids, "embedding": embeddings}).to_json(
        embeddings_path, orient="records", lines=True
    )
    return str(documents_path), str(embeddings_path)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store_module, "SentenceTransformer", _FakeSentenceTransformer)

    documents_path, embeddings_path = _write_store_files(
        tmp_path,
        ids=["doc-apple", "doc-orange"],
        documents=["Apples are a fruit.", "Oranges are a citrus fruit."],
        metadatas=[{"source": "fruit.pdf"}, {"source": "fruit.pdf"}],
        embedding_ids=["doc-apple", "doc-orange"],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    )
    return VectorStore(documents_source=documents_path, embeddings_source=embeddings_path)


def test_get_similar_documents_returns_closest_match_in_rank_order(store):
    assert store.get_similar_documents("query about apples", k=5) == ["Apples are a fruit."]


def test_get_similar_documents_filters_out_dissimilar_results(store):
    assert store.get_similar_documents("totally unrelated", k=5) == []


def test_document_exists_checks_metadata_source(store):
    assert store.document_exists("fruit.pdf") is True
    assert store.document_exists("other.pdf") is False


def test_get_random_document_returns_a_row(store):
    doc = store.get_random_document()
    assert doc["documents"] in {"Apples are a fruit.", "Oranges are a citrus fruit."}


def test_mismatched_ids_between_documents_and_embeddings_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store_module, "SentenceTransformer", _FakeSentenceTransformer)

    documents_path, embeddings_path = _write_store_files(
        tmp_path,
        ids=["a", "b"],
        documents=["A", "B"],
        metadatas=[{}, {}],
        embedding_ids=["b", "a"],
        embeddings=[[1.0], [0.0]],
    )

    with pytest.raises(RuntimeError):
        VectorStore(documents_source=documents_path, embeddings_source=embeddings_path)
