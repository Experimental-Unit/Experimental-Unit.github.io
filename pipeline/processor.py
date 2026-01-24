"""Document processing and chunking for the pipeline."""

import re
import hashlib
from typing import Optional
from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from .loader import SubstackPost
from .config import Config, default_config


@dataclass
class ProcessedChunk:
    """A processed chunk of a document."""

    chunk_id: str
    post_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None

    def to_langchain_doc(self) -> Document:
        """Convert to LangChain Document."""
        return Document(
            page_content=self.content,
            metadata={
                "chunk_id": self.chunk_id,
                "post_id": self.post_id,
                **self.metadata,
            },
        )


class DocumentProcessor:
    """Process Substack posts into chunks for embedding."""

    def __init__(self, config: Config = default_config):
        self.config = config
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.processing.chunk_size,
            chunk_overlap=config.processing.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def process_post(self, post: SubstackPost) -> list[ProcessedChunk]:
        """Process a single post into chunks."""
        # Clean the content
        content = self._clean_content(post.content)

        # Skip if too short
        if len(content) < self.config.processing.min_chunk_size:
            return []

        # Split into chunks
        chunks = self.text_splitter.split_text(content)

        # Create ProcessedChunk objects
        processed_chunks = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = self._generate_chunk_id(post.id, i)

            metadata = {
                "title": post.title,
                "author": post.author,
                "published_date": post.published_date.isoformat() if post.published_date else None,
                "url": post.url,
                "subtitle": post.subtitle,
                "tags": post.tags,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "word_count": len(chunk_text.split()),
                "source_file": post.source_file,
            }

            processed_chunks.append(
                ProcessedChunk(
                    chunk_id=chunk_id,
                    post_id=post.id,
                    content=chunk_text,
                    metadata=metadata,
                )
            )

        return processed_chunks

    def process_posts(self, posts: list[SubstackPost]) -> list[ProcessedChunk]:
        """Process multiple posts into chunks."""
        all_chunks = []
        for post in posts:
            chunks = self.process_post(post)
            all_chunks.extend(chunks)
        return all_chunks

    def _clean_content(self, content: str) -> str:
        """Clean and normalize content."""
        # Remove excessive whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)

        # Remove common Substack artifacts
        content = re.sub(r"Subscribe\s*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"Share\s*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"Leave a comment\s*$", "", content, flags=re.MULTILINE)

        # Clean up markdown artifacts
        content = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", content)  # Remove image links

        return content.strip()

    def _generate_chunk_id(self, post_id: str, chunk_index: int) -> str:
        """Generate a unique chunk ID."""
        content = f"{post_id}_{chunk_index}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def to_langchain_docs(self, chunks: list[ProcessedChunk]) -> list[Document]:
        """Convert processed chunks to LangChain Documents."""
        return [chunk.to_langchain_doc() for chunk in chunks]


class ContentAnalyzer:
    """Analyze content for additional metadata extraction."""

    def extract_key_phrases(self, text: str, top_n: int = 10) -> list[str]:
        """Extract key phrases from text using simple heuristics."""
        # Simple extraction based on capitalized phrases and frequency
        words = text.split()
        phrases = []

        # Find capitalized sequences (potential proper nouns/concepts)
        current_phrase = []
        for word in words:
            clean_word = re.sub(r"[^\w]", "", word)
            if clean_word and clean_word[0].isupper():
                current_phrase.append(word)
            else:
                if len(current_phrase) >= 2:
                    phrases.append(" ".join(current_phrase))
                current_phrase = []

        # Count frequency and return top N
        from collections import Counter
        phrase_counts = Counter(phrases)
        return [phrase for phrase, _ in phrase_counts.most_common(top_n)]

    def estimate_reading_time(self, text: str, wpm: int = 200) -> int:
        """Estimate reading time in minutes."""
        word_count = len(text.split())
        return max(1, round(word_count / wpm))

    def detect_content_type(self, text: str) -> str:
        """Detect the type of content (article, tutorial, review, etc.)."""
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["step 1", "how to", "tutorial", "guide"]):
            return "tutorial"
        elif any(kw in text_lower for kw in ["review", "rating", "pros and cons"]):
            return "review"
        elif any(kw in text_lower for kw in ["interview", "q:", "a:"]):
            return "interview"
        elif any(kw in text_lower for kw in ["announcement", "launching", "introducing"]):
            return "announcement"
        else:
            return "article"
