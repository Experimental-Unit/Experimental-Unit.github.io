"""Document loaders for various Substack export formats."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
import html2text
import frontmatter


@dataclass
class SubstackPost:
    """Represents a single Substack post."""

    id: str
    title: str
    content: str  # Plain text content
    html_content: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    url: Optional[str] = None
    subtitle: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    word_count: int = 0
    source_file: Optional[str] = None

    def __post_init__(self):
        if not self.word_count:
            self.word_count = len(self.content.split())

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "url": self.url,
            "subtitle": self.subtitle,
            "tags": self.tags,
            "word_count": self.word_count,
            "source_file": self.source_file,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubstackPost":
        """Create from dictionary."""
        if data.get("published_date"):
            data["published_date"] = datetime.fromisoformat(data["published_date"])
        return cls(**data)


class SubstackLoader:
    """Load Substack posts from various formats."""

    def __init__(self, input_dir: Path):
        self.input_dir = Path(input_dir)
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.body_width = 0  # No wrapping

    def load_all(self) -> list[SubstackPost]:
        """Load all posts from the input directory."""
        posts = []

        # Try different file patterns
        for pattern in ["*.html", "*.htm", "*.md", "*.json"]:
            for file_path in self.input_dir.glob(f"**/{pattern}"):
                try:
                    post = self.load_file(file_path)
                    if post:
                        posts.append(post)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")

        return posts

    def load_file(self, file_path: Path) -> Optional[SubstackPost]:
        """Load a single file based on its extension."""
        suffix = file_path.suffix.lower()

        if suffix in [".html", ".htm"]:
            return self._load_html(file_path)
        elif suffix == ".md":
            return self._load_markdown(file_path)
        elif suffix == ".json":
            return self._load_json(file_path)

        return None

    def _load_html(self, file_path: Path) -> SubstackPost:
        """Load from HTML file."""
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract title
        title = ""
        title_elem = soup.find("h1") or soup.find("title")
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Extract main content
        # Try common Substack content containers
        content_elem = (
            soup.find("div", class_="body") or
            soup.find("article") or
            soup.find("div", class_="post-content") or
            soup.find("div", class_="available-content") or
            soup.body
        )

        html_body = str(content_elem) if content_elem else html_content
        content = self.html_converter.handle(html_body).strip()

        # Extract metadata
        author = None
        author_elem = soup.find("meta", {"name": "author"})
        if author_elem:
            author = author_elem.get("content")

        # Extract date
        date = None
        date_elem = soup.find("time") or soup.find("meta", {"property": "article:published_time"})
        if date_elem:
            date_str = date_elem.get("datetime") or date_elem.get("content")
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Extract subtitle
        subtitle = None
        subtitle_elem = soup.find("h2", class_="subtitle") or soup.find("p", class_="subtitle")
        if subtitle_elem:
            subtitle = subtitle_elem.get_text(strip=True)

        # Generate ID from filename
        post_id = file_path.stem

        return SubstackPost(
            id=post_id,
            title=title or post_id,
            content=content,
            html_content=html_content,
            author=author,
            published_date=date,
            subtitle=subtitle,
            source_file=str(file_path),
        )

    def _load_markdown(self, file_path: Path) -> SubstackPost:
        """Load from Markdown file with optional frontmatter."""
        with open(file_path, "r", encoding="utf-8") as f:
            post = frontmatter.load(f)

        content = post.content
        metadata = post.metadata

        # Extract from frontmatter
        title = metadata.get("title", file_path.stem)
        author = metadata.get("author")
        date = metadata.get("date") or metadata.get("published_date")
        subtitle = metadata.get("subtitle") or metadata.get("description")
        tags = metadata.get("tags", [])
        url = metadata.get("url") or metadata.get("canonical_url")

        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
            except ValueError:
                date = None

        return SubstackPost(
            id=file_path.stem,
            title=title,
            content=content,
            author=author,
            published_date=date,
            url=url,
            subtitle=subtitle,
            tags=tags if isinstance(tags, list) else [tags],
            source_file=str(file_path),
        )

    def _load_json(self, file_path: Path) -> Optional[SubstackPost]:
        """Load from JSON file (Substack export format)."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle both single post and array of posts
        if isinstance(data, list):
            # Return first post; caller should handle multiple
            if not data:
                return None
            data = data[0]

        # Map Substack export fields
        content = data.get("body_text") or data.get("content") or ""
        html_content = data.get("body_html") or data.get("html")

        if not content and html_content:
            content = self.html_converter.handle(html_content).strip()

        date = None
        date_str = data.get("post_date") or data.get("published_at") or data.get("date")
        if date_str:
            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return SubstackPost(
            id=data.get("id") or data.get("slug") or file_path.stem,
            title=data.get("title", file_path.stem),
            content=content,
            html_content=html_content,
            author=data.get("author") or data.get("author_name"),
            published_date=date,
            url=data.get("canonical_url") or data.get("url"),
            subtitle=data.get("subtitle") or data.get("description"),
            tags=data.get("tags", []),
            source_file=str(file_path),
        )

    def load_from_text(self, text: str, title: str = "Untitled", post_id: Optional[str] = None) -> SubstackPost:
        """Load a post from raw text (for manual input)."""
        return SubstackPost(
            id=post_id or title.lower().replace(" ", "-"),
            title=title,
            content=text,
        )

    def iter_posts(self) -> Iterator[SubstackPost]:
        """Iterate over posts one at a time (memory efficient)."""
        for pattern in ["*.html", "*.htm", "*.md", "*.json"]:
            for file_path in self.input_dir.glob(f"**/{pattern}"):
                try:
                    post = self.load_file(file_path)
                    if post:
                        yield post
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
