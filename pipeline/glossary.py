"""Glossary extraction and term management."""

import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .config import Config, default_config
from .summarizer import get_llm
from .loader import SubstackPost


@dataclass
class GlossaryTerm:
    """A term in the glossary."""

    term: str
    definition: str
    category: str = "general"
    related_terms: list[str] = field(default_factory=list)
    source_posts: list[str] = field(default_factory=list)  # Post IDs where term appears
    first_seen: Optional[str] = None  # Post ID where first defined/introduced
    usage_count: int = 1
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GlossaryTerm":
        return cls(**data)


class GlossaryExtractor:
    """Extract and manage glossary terms from posts."""

    def __init__(self, config: Config = default_config):
        self.config = config
        self.llm = get_llm(config)
        self.terms: dict[str, GlossaryTerm] = {}

        self.extraction_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert at identifying and defining key terms, concepts, and jargon.
Extract terms that would be valuable for a glossary - focus on:
- Technical terms and jargon
- Named concepts or frameworks
- Acronyms and abbreviations
- Domain-specific vocabulary
- Novel terms coined by the author""",
                ),
                (
                    "human",
                    """Extract glossary terms from this post.

Title: {title}
Content:
{content}

Return JSON array of terms:
[
    {{
        "term": "Term Name",
        "definition": "Clear, concise definition based on context",
        "category": "One of: concept, technical, framework, person, organization, acronym, other",
        "related_terms": ["Related Term 1", "Related Term 2"],
        "aliases": ["Alternative name", "Abbreviation"]
    }}
]

Extract 5-20 relevant terms. Be selective - only include terms that would genuinely help a reader understand the content.""",
                ),
            ]
        )

        self.chain = self.extraction_prompt | self.llm | StrOutputParser()

    def extract_from_post(self, post: SubstackPost) -> list[GlossaryTerm]:
        """Extract glossary terms from a single post."""
        content = post.content
        if len(content) > 12000:
            content = content[:12000]

        response = self.chain.invoke(
            {
                "title": post.title,
                "content": content,
            }
        )

        # Parse response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            terms_data = json.loads(response)
        except json.JSONDecodeError:
            return []

        terms = []
        for data in terms_data:
            term = GlossaryTerm(
                term=data.get("term", ""),
                definition=data.get("definition", ""),
                category=data.get("category", "general"),
                related_terms=data.get("related_terms", []),
                aliases=data.get("aliases", []),
                source_posts=[post.id],
                first_seen=post.id,
            )
            terms.append(term)

        return terms

    def extract_from_posts(
        self, posts: list[SubstackPost], progress_callback=None
    ) -> dict[str, GlossaryTerm]:
        """Extract and merge glossary terms from multiple posts."""
        total = len(posts)

        for i, post in enumerate(posts):
            try:
                terms = self.extract_from_post(post)
                self._merge_terms(terms)

                if progress_callback:
                    progress_callback(i + 1, total, post.title)
                else:
                    print(f"[{i + 1}/{total}] Extracted terms from: {post.title}")

            except Exception as e:
                print(f"Error extracting from '{post.title}': {e}")

        return self.terms

    def _merge_terms(self, new_terms: list[GlossaryTerm]):
        """Merge new terms into existing glossary."""
        for term in new_terms:
            key = self._normalize_term(term.term)

            if key in self.terms:
                # Update existing term
                existing = self.terms[key]
                existing.usage_count += 1

                # Add source post if not already present
                for post_id in term.source_posts:
                    if post_id not in existing.source_posts:
                        existing.source_posts.append(post_id)

                # Merge related terms
                for related in term.related_terms:
                    if related not in existing.related_terms:
                        existing.related_terms.append(related)

                # Merge aliases
                for alias in term.aliases:
                    if alias not in existing.aliases:
                        existing.aliases.append(alias)

                # Keep better definition (longer usually means more complete)
                if len(term.definition) > len(existing.definition):
                    existing.definition = term.definition
            else:
                # Add new term
                self.terms[key] = term

            # Also index by aliases
            for alias in term.aliases:
                alias_key = self._normalize_term(alias)
                if alias_key not in self.terms:
                    # Create reference to main term
                    self.terms[alias_key] = term

    def _normalize_term(self, term: str) -> str:
        """Normalize term for consistent lookup."""
        return term.lower().strip()

    def get_term(self, term: str) -> Optional[GlossaryTerm]:
        """Look up a term in the glossary."""
        key = self._normalize_term(term)
        return self.terms.get(key)

    def get_terms_by_category(self, category: str) -> list[GlossaryTerm]:
        """Get all terms in a category."""
        return [t for t in self.terms.values() if t.category == category]

    def get_most_common_terms(self, n: int = 20) -> list[GlossaryTerm]:
        """Get the most frequently used terms."""
        unique_terms = list({id(t): t for t in self.terms.values()}.values())
        return sorted(unique_terms, key=lambda t: t.usage_count, reverse=True)[:n]

    def export(self, output_dir: Path):
        """Export glossary to various formats."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get unique terms (avoid duplicates from aliases)
        unique_terms = list({id(t): t for t in self.terms.values()}.values())
        unique_terms.sort(key=lambda t: t.term.lower())

        # JSON export
        glossary_data = [t.to_dict() for t in unique_terms]
        with open(output_dir / "glossary.json", "w") as f:
            json.dump(glossary_data, f, indent=2)

        # Markdown export
        self._export_markdown(unique_terms, output_dir / "glossary.md")

        # By-category export
        self._export_by_category(unique_terms, output_dir / "glossary_by_category.md")

        print(f"Exported {len(unique_terms)} glossary terms")

    def _export_markdown(self, terms: list[GlossaryTerm], output_path: Path):
        """Export glossary as markdown."""
        lines = ["# Glossary\n"]

        current_letter = ""
        for term in terms:
            first_letter = term.term[0].upper()
            if first_letter != current_letter:
                current_letter = first_letter
                lines.append(f"\n## {current_letter}\n")

            lines.append(f"### {term.term}")
            lines.append(f"{term.definition}\n")

            if term.aliases:
                lines.append(f"*Also known as: {', '.join(term.aliases)}*\n")

            if term.related_terms:
                lines.append(f"**Related:** {', '.join(term.related_terms)}\n")

            lines.append(f"*Category: {term.category} | Appears in {term.usage_count} post(s)*\n")
            lines.append("")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

    def _export_by_category(self, terms: list[GlossaryTerm], output_path: Path):
        """Export glossary organized by category."""
        by_category = defaultdict(list)
        for term in terms:
            by_category[term.category].append(term)

        lines = ["# Glossary by Category\n"]

        for category in sorted(by_category.keys()):
            lines.append(f"\n## {category.title()}\n")
            for term in sorted(by_category[category], key=lambda t: t.term.lower()):
                lines.append(f"- **{term.term}**: {term.definition}")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

    def load(self, input_path: Path):
        """Load glossary from JSON file."""
        with open(input_path, "r") as f:
            data = json.load(f)

        self.terms = {}
        for item in data:
            term = GlossaryTerm.from_dict(item)
            key = self._normalize_term(term.term)
            self.terms[key] = term

            # Also index aliases
            for alias in term.aliases:
                alias_key = self._normalize_term(alias)
                self.terms[alias_key] = term
