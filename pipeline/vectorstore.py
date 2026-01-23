"""Vector store management for semantic search."""

import json
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .config import Config, default_config
from .processor import ProcessedChunk


def get_embeddings(config: Config) -> Embeddings:
    """Get embeddings based on configuration."""
    provider = config.embedding.provider
    model_name = config.embedding.model_name

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=model_name,
            openai_api_key=config.openai_api_key,
        )
    elif provider == "huggingface":
        from langchain_community.embeddings import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    elif provider == "ollama":
        from langchain_community.embeddings import OllamaEmbeddings

        return OllamaEmbeddings(model=model_name)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


class VectorStoreManager:
    """Manage the vector store for semantic search."""

    def __init__(self, config: Config = default_config):
        self.config = config
        self.embeddings = get_embeddings(config)
        self.vectorstore = None
        self._load_or_create()

    def _load_or_create(self):
        """Load existing vector store or create new one."""
        from langchain_community.vectorstores import Chroma

        persist_dir = str(self.config.vectorstore_path)
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self.vectorstore = Chroma(
            collection_name=self.config.collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_dir,
        )

    def add_documents(self, documents: list[Document], batch_size: int = 100):
        """Add documents to the vector store in batches."""
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            self.vectorstore.add_documents(batch)
            print(f"Added batch {i // batch_size + 1}/{(len(documents) - 1) // batch_size + 1}")

    def add_chunks(self, chunks: list[ProcessedChunk], batch_size: int = 100):
        """Add processed chunks to the vector store."""
        documents = [chunk.to_langchain_doc() for chunk in chunks]
        self.add_documents(documents, batch_size)

    def search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[dict] = None,
    ) -> list[Document]:
        """Search for similar documents."""
        if filter_dict:
            return self.vectorstore.similarity_search(query, k=k, filter=filter_dict)
        return self.vectorstore.similarity_search(query, k=k)

    def search_with_score(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[dict] = None,
    ) -> list[tuple[Document, float]]:
        """Search for similar documents with relevance scores."""
        if filter_dict:
            return self.vectorstore.similarity_search_with_score(query, k=k, filter=filter_dict)
        return self.vectorstore.similarity_search_with_score(query, k=k)

    def get_retriever(self, search_kwargs: Optional[dict] = None):
        """Get a retriever for use in chains."""
        search_kwargs = search_kwargs or {"k": 5}
        return self.vectorstore.as_retriever(search_kwargs=search_kwargs)

    def delete_by_post_id(self, post_id: str):
        """Delete all chunks for a specific post."""
        # Get all documents with this post_id
        results = self.vectorstore.get(where={"post_id": post_id})
        if results and results.get("ids"):
            self.vectorstore.delete(ids=results["ids"])

    def get_stats(self) -> dict:
        """Get statistics about the vector store."""
        collection = self.vectorstore._collection
        count = collection.count()

        return {
            "total_documents": count,
            "collection_name": self.config.collection_name,
            "embedding_model": self.config.embedding.model_name,
        }

    def export_metadata(self, output_path: Path):
        """Export all document metadata to JSON."""
        results = self.vectorstore.get(include=["metadatas"])

        metadata_list = results.get("metadatas", [])
        ids = results.get("ids", [])

        export_data = [
            {"id": doc_id, "metadata": meta} for doc_id, meta in zip(ids, metadata_list)
        ]

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)


class SearchIndex:
    """Create and manage a search index for the static site."""

    def __init__(self, config: Config = default_config):
        self.config = config
        self.index_data = []

    def build_from_posts(self, posts: list) -> list[dict]:
        """Build search index from posts."""
        self.index_data = []

        for post in posts:
            entry = {
                "id": post.id,
                "title": post.title,
                "subtitle": post.subtitle or "",
                "content_preview": post.content[:500] if post.content else "",
                "author": post.author or "",
                "date": post.published_date.isoformat() if post.published_date else "",
                "tags": post.tags,
                "url": post.url or f"/posts/{post.id}.html",
                "word_count": post.word_count,
            }
            self.index_data.append(entry)

        return self.index_data

    def export(self, output_path: Path):
        """Export search index to JSON."""
        with open(output_path, "w") as f:
            json.dump(self.index_data, f, indent=2)

    def export_lunr_index(self, output_path: Path):
        """Export index in Lunr.js compatible format."""
        # Simplified format for client-side search
        lunr_docs = []
        for entry in self.index_data:
            lunr_docs.append(
                {
                    "id": entry["id"],
                    "title": entry["title"],
                    "body": entry["content_preview"],
                    "tags": " ".join(entry["tags"]),
                }
            )

        with open(output_path, "w") as f:
            json.dump(lunr_docs, f)
