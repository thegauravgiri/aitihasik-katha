from functools import lru_cache

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from ..core.logging import get_logger
from ..core.settings import settings


logger = get_logger(__name__)


class VectorStore:
    """Local FAISS-backed vector store for retrieval.

    `documents_source` holds each chunk's text + metadata; `embeddings_source`
    holds the matching precomputed embedding vectors (same row order/ids, as
    produced by the ingestion pipeline). Similarity is cosine similarity,
    computed as inner product over L2-normalized vectors.
    """

    def __init__(
        self,
        documents_source: str = "data/embeddings/nepali-history.json",
        embeddings_source: str = "data/embeddings/history.json",
    ) -> None:
        self.df = pd.read_json(documents_source, lines=True, orient="records")
        embeddings_df = pd.read_json(embeddings_source, lines=True, orient="records")

        if not (self.df["ids"].astype(str) == embeddings_df["id"].astype(str)).all():
            raise RuntimeError(
                f"{documents_source} and {embeddings_source} are out of sync: "
                "row ids don't line up positionally."
            )

        embeddings = np.array(embeddings_df["embedding"].tolist(), dtype="float32")
        faiss.normalize_L2(embeddings)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        logger.info(
            "Loaded FAISS index with %s vectors (dim=%s) from %s",
            self.index.ntotal, embeddings.shape[1], embeddings_source,
        )

        model_name = settings.EMBEDDING_MODEL or "sentence-transformers/all-MiniLM-L6-v2"
        self.model = SentenceTransformer(model_name)

    def __len__(self) -> int:
        return len(self.df)

    def get_document_by_id(self, idx: str) -> str:
        return self.df[self.df["ids"] == idx].iloc[0]["documents"]

    def get_document_by_ids(self, ids: list[str]) -> list[str]:
        return self.df[self.df["ids"].isin(ids)]["documents"].to_list()

    def get_embeddings(self, text: str) -> list[float]:
        return self.model.encode(str(text)).tolist()

    def get_similar_documents(self, query: str, k: int = 50, similarity_threshold: float = 0.6) -> list[str]:
        query_embedding = np.array([self.get_embeddings(query)], dtype="float32")
        faiss.normalize_L2(query_embedding)
        similarities, indices = self.index.search(query_embedding, k)

        matched_positions = [
            int(position)
            for position, similarity in zip(indices[0], similarities[0])
            if position != -1 and similarity > similarity_threshold
        ]
        return self.df.iloc[matched_positions]["documents"].to_list()

    def document_exists(self, source: str) -> bool:
        if "metadatas" not in self.df.columns:
            return False
        metadata_sources = self.df["metadatas"].apply(
            lambda value: value.get("source") if isinstance(value, dict) else None
        )
        return bool((metadata_sources == source).any())

    def add_document(self, source: str, chunks: list) -> None:
        raise NotImplementedError(
            "Adding new documents requires re-embedding and rebuilding the FAISS index: "
            "regenerate data/embeddings/*.json via the ingestion pipeline, then restart."
        )

    def add_new_source(self, source: str) -> None:
        raise NotImplementedError("Source ingestion is handled by dedicated ingestion modules.")

    def remove_source(self, source: str) -> None:
        raise NotImplementedError("Source deletion is not implemented.")

    def get_random_document(self) -> pd.Series:
        randomly_selected = self.df.sample(1)
        return randomly_selected.iloc[0]


@lru_cache(maxsize=1)
def get_store() -> VectorStore:
    """Lazily construct the shared vector store on first use."""
    return VectorStore()
