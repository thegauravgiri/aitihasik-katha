from functools import lru_cache

import pandas as pd
from google.cloud import aiplatform
from sentence_transformers import SentenceTransformer

from ..core.settings import settings


class VectorStore:
    """Thin adapter around Vertex AI Matching Engine for retrieval."""

    def __init__(self, source: str = "data/embeddings/nepali-history.json") -> None:
        settings.require("PROJECT_ID", "LOCATION", "INDEX_ID", "INDEX_ENDPOINT_ID")
        self.df = pd.read_json(source, lines=True, orient="records")

        aiplatform.init(
            project=settings.PROJECT_ID,
            location=settings.LOCATION,
        )
        self.index = aiplatform.MatchingEngineIndex(settings.INDEX_ID)
        self.index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
            settings.INDEX_ENDPOINT_ID
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

    def get_similar_documents(self, query: str, k: int = 50) -> list[str]:
        query_embedding = self.get_embeddings(query)
        response = self.index_endpoint.find_neighbors(
            deployed_index_id=settings.DEPLOYED_INDEX_ID,
            queries=[query_embedding],
            num_neighbors=k,
        )
        ids = [resp.id for resp in response[0] if resp.distance > 0.6]
        return self.get_document_by_ids(ids)

    def document_exists(self, source: str) -> bool:
        if "metadatas" not in self.df.columns:
            return False
        metadata_sources = self.df["metadatas"].apply(
            lambda value: value.get("source") if isinstance(value, dict) else None
        )
        return bool((metadata_sources == source).any())

    def add_document(self, source: str, chunks: list) -> None:
        raise NotImplementedError(
            "Adding new vectors to Matching Engine is not implemented yet. "
            "Populate embeddings through your ingestion pipeline and indexing job."
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
    """Lazily construct the shared vector store on first use.

    Deferring construction (rather than instantiating a module-level
    singleton at import time) avoids requiring valid Vertex AI credentials
    just to import this module.
    """
    return VectorStore()
