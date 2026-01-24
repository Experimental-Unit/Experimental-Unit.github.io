"""
Enhanced Entity Extraction for building comprehensive glossaries.

Extracts multiple entity types:
- People (names, roles, affiliations)
- Organizations (companies, institutions, groups)
- Places (locations, regions, countries)
- Concepts (abstract ideas, theories, methodologies)
- Technical Terms (jargon, domain-specific vocabulary)
- Events (historical events, milestones)
- Works (books, papers, products, projects)
- Acronyms (abbreviations with expansions)
"""

import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .config import Config, default_config
from .summarizer import get_llm


@dataclass
class Entity:
    """A single extracted entity."""

    name: str
    entity_type: str  # person, organization, place, concept, technical_term, event, work, acronym
    definition: str
    context: str = ""  # Original context where found
    aliases: list[str] = field(default_factory=list)
    related_entities: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    occurrence_count: int = 1
    importance_score: float = 0.0  # 0-1 score based on frequency and context
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        return cls(**data)


class EntityExtractor:
    """
    Extract entities from text using LLM-based analysis.

    Designed for processing large volumes of text from multiple files.
    """

    ENTITY_TYPES = [
        "person",
        "organization",
        "place",
        "concept",
        "technical_term",
        "event",
        "work",
        "acronym",
    ]

    def __init__(self, config: Config = default_config, batch_size: int = 3):
        self.config = config
        self.llm = get_llm(config)
        self.batch_size = batch_size
        self.entities: dict[str, Entity] = {}

        # Main extraction prompt
        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert entity extraction system. Your task is to identify and extract all notable entities from text.

Extract these entity types:
1. PERSON - Named individuals (include role/title if mentioned)
2. ORGANIZATION - Companies, institutions, teams, groups
3. PLACE - Cities, countries, regions, specific locations
4. CONCEPT - Abstract ideas, theories, philosophies, methodologies
5. TECHNICAL_TERM - Domain-specific jargon, technical vocabulary, specialized terms
6. EVENT - Historical events, conferences, milestones
7. WORK - Books, papers, articles, products, projects, tools
8. ACRONYM - Abbreviations with their full expansions

For each entity, provide:
- A clear, concise definition based on the context
- Any aliases or alternative names mentioned
- Related entities that appear together

Be thorough but precise. Only extract entities that are clearly identifiable."""),
            ("human", """Extract all entities from this text:

Source: {source_name}

Text:
{text}

Return a JSON array of entities:
[
    {{
        "name": "Entity Name",
        "entity_type": "person|organization|place|concept|technical_term|event|work|acronym",
        "definition": "Brief definition based on context",
        "context": "The sentence or phrase where this entity appears",
        "aliases": ["Alternative Name", "Abbreviation"],
        "related_entities": ["Related Entity 1", "Related Entity 2"]
    }}
]

Extract ALL notable entities. Aim for 10-50 entities depending on text length and density.""")
        ])

        self.chain = self.extraction_prompt | self.llm | StrOutputParser()

    def extract_from_text(
        self,
        text: str,
        source_name: str = "unknown",
        max_chunk_size: int = 8000
    ) -> list[Entity]:
        """
        Extract entities from a single text.

        For long texts, splits into chunks and processes each.
        """
        # Split long texts into manageable chunks
        chunks = self._split_text(text, max_chunk_size)
        all_entities = []

        for i, chunk in enumerate(chunks):
            chunk_source = f"{source_name}" if len(chunks) == 1 else f"{source_name} (part {i+1}/{len(chunks)})"

            try:
                entities = self._extract_from_chunk(chunk, chunk_source)
                all_entities.extend(entities)
            except Exception as e:
                print(f"  Warning: Error extracting from {chunk_source}: {e}")

        return all_entities

    def _split_text(self, text: str, max_size: int) -> list[str]:
        """Split text into chunks at natural boundaries."""
        if len(text) <= max_size:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by paragraphs first
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _extract_from_chunk(self, text: str, source_name: str) -> list[Entity]:
        """Extract entities from a single text chunk."""
        response = self.chain.invoke({
            "text": text,
            "source_name": source_name
        })

        # Parse JSON response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            entities_data = json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON array in response
            match = re.search(r'\[[\s\S]*\]', response)
            if match:
                try:
                    entities_data = json.loads(match.group())
                except:
                    return []
            else:
                return []

        entities = []
        for data in entities_data:
            if not data.get("name") or not data.get("entity_type"):
                continue

            entity = Entity(
                name=data.get("name", "").strip(),
                entity_type=data.get("entity_type", "concept").lower(),
                definition=data.get("definition", ""),
                context=data.get("context", ""),
                aliases=data.get("aliases", []),
                related_entities=data.get("related_entities", []),
                source_files=[source_name],
            )
            entities.append(entity)

        return entities

    def process_files(
        self,
        files: list[Path],
        progress_callback=None
    ) -> dict[str, Entity]:
        """
        Process multiple files and build merged entity glossary.

        Args:
            files: List of file paths to process
            progress_callback: Optional callback(current, total, filename)

        Returns:
            Dictionary of normalized entity name -> Entity
        """
        total = len(files)

        for i, file_path in enumerate(files):
            try:
                # Read file content
                text = self._read_file(file_path)
                if not text or len(text.strip()) < 50:
                    if progress_callback:
                        progress_callback(i + 1, total, file_path.name, 0)
                    continue

                # Extract entities
                entities = self.extract_from_text(text, file_path.name)

                # Merge into global glossary
                self._merge_entities(entities)

                if progress_callback:
                    progress_callback(i + 1, total, file_path.name, len(entities))
                else:
                    print(f"[{i + 1}/{total}] {file_path.name}: {len(entities)} entities")

            except Exception as e:
                print(f"Error processing {file_path.name}: {e}")

        # Calculate importance scores
        self._calculate_importance_scores()

        return self.entities

    def _read_file(self, file_path: Path) -> str:
        """Read content from a text or markdown file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Strip YAML frontmatter from markdown files
            if file_path.suffix.lower() in ['.md', '.markdown']:
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        content = parts[2]

            return content
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return ""

    def _merge_entities(self, new_entities: list[Entity]):
        """Merge new entities into the global glossary."""
        for entity in new_entities:
            key = self._normalize_name(entity.name)

            if key in self.entities:
                existing = self.entities[key]
                existing.occurrence_count += 1

                # Add source files
                for source in entity.source_files:
                    if source not in existing.source_files:
                        existing.source_files.append(source)

                # Merge aliases
                for alias in entity.aliases:
                    if alias and alias not in existing.aliases:
                        existing.aliases.append(alias)

                # Merge related entities
                for related in entity.related_entities:
                    if related and related not in existing.related_entities:
                        existing.related_entities.append(related)

                # Keep better definition (longer = more complete)
                if len(entity.definition) > len(existing.definition):
                    existing.definition = entity.definition

                # Update context if current is empty
                if not existing.context and entity.context:
                    existing.context = entity.context
            else:
                self.entities[key] = entity

            # Also index by aliases
            for alias in entity.aliases:
                if alias:
                    alias_key = self._normalize_name(alias)
                    if alias_key not in self.entities:
                        self.entities[alias_key] = entity

    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for consistent lookup."""
        return name.lower().strip()

    def _calculate_importance_scores(self):
        """Calculate importance scores based on frequency and connections."""
        if not self.entities:
            return

        max_occurrences = max(e.occurrence_count for e in self.entities.values())
        max_sources = max(len(e.source_files) for e in self.entities.values())
        max_relations = max(len(e.related_entities) for e in self.entities.values()) or 1

        for entity in self.entities.values():
            # Weighted score: occurrences (40%) + sources (40%) + relations (20%)
            occ_score = entity.occurrence_count / max_occurrences if max_occurrences > 0 else 0
            src_score = len(entity.source_files) / max_sources if max_sources > 0 else 0
            rel_score = len(entity.related_entities) / max_relations if max_relations > 0 else 0

            entity.importance_score = round(0.4 * occ_score + 0.4 * src_score + 0.2 * rel_score, 3)

    def get_unique_entities(self) -> list[Entity]:
        """Get deduplicated list of entities."""
        seen_ids = set()
        unique = []
        for entity in self.entities.values():
            entity_id = id(entity)
            if entity_id not in seen_ids:
                seen_ids.add(entity_id)
                unique.append(entity)
        return unique

    def get_entities_by_type(self, entity_type: str) -> list[Entity]:
        """Get all entities of a specific type."""
        return [e for e in self.get_unique_entities() if e.entity_type == entity_type]

    def get_top_entities(self, n: int = 50) -> list[Entity]:
        """Get top N entities by importance score."""
        unique = self.get_unique_entities()
        return sorted(unique, key=lambda e: e.importance_score, reverse=True)[:n]

    def search(self, query: str) -> list[Entity]:
        """Search entities by name or definition."""
        query_lower = query.lower()
        results = []

        for entity in self.get_unique_entities():
            if query_lower in entity.name.lower():
                results.append((entity, 1.0))
            elif any(query_lower in alias.lower() for alias in entity.aliases):
                results.append((entity, 0.8))
            elif query_lower in entity.definition.lower():
                results.append((entity, 0.5))

        results.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in results]


class GlossaryBuilder:
    """Build and export glossaries from extracted entities."""

    def __init__(self, entities: dict[str, Entity]):
        self.entities = entities

    def get_unique_entities(self) -> list[Entity]:
        """Get deduplicated, sorted list of entities."""
        seen_ids = set()
        unique = []
        for entity in self.entities.values():
            entity_id = id(entity)
            if entity_id not in seen_ids:
                seen_ids.add(entity_id)
                unique.append(entity)
        return sorted(unique, key=lambda e: e.name.lower())

    def export_all(self, output_dir: Path):
        """Export glossary in all formats."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        unique = self.get_unique_entities()

        # JSON export
        self._export_json(unique, output_dir / "entity_glossary.json")

        # Markdown exports
        self._export_markdown_full(unique, output_dir / "glossary.md")
        self._export_markdown_by_type(unique, output_dir / "glossary_by_type.md")
        self._export_markdown_top(unique, output_dir / "glossary_top_terms.md")

        # Stats
        self._export_stats(unique, output_dir / "extraction_stats.json")

        return len(unique)

    def _export_json(self, entities: list[Entity], path: Path):
        """Export full glossary as JSON."""
        data = [e.to_dict() for e in entities]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Exported JSON: {path}")

    def _export_markdown_full(self, entities: list[Entity], path: Path):
        """Export complete glossary as markdown."""
        lines = [
            "# Entity Glossary",
            "",
            f"*{len(entities)} entities extracted*",
            "",
            "---",
            ""
        ]

        current_letter = ""
        for entity in entities:
            first_letter = entity.name[0].upper() if entity.name else "?"
            if first_letter != current_letter:
                current_letter = first_letter
                lines.append(f"\n## {current_letter}\n")

            # Entity header with type badge
            type_emoji = self._get_type_emoji(entity.entity_type)
            lines.append(f"### {entity.name} {type_emoji}")
            lines.append("")
            lines.append(f"**Type:** {entity.entity_type.replace('_', ' ').title()}")
            lines.append("")
            lines.append(entity.definition)
            lines.append("")

            if entity.aliases:
                lines.append(f"*Also known as: {', '.join(entity.aliases)}*")
                lines.append("")

            if entity.related_entities:
                lines.append(f"**Related:** {', '.join(entity.related_entities[:5])}")
                lines.append("")

            lines.append(f"*Appears in {entity.occurrence_count} location(s) across {len(entity.source_files)} file(s)*")
            lines.append("")

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"  Exported Markdown: {path}")

    def _export_markdown_by_type(self, entities: list[Entity], path: Path):
        """Export glossary organized by entity type."""
        by_type = defaultdict(list)
        for entity in entities:
            by_type[entity.entity_type].append(entity)

        lines = [
            "# Glossary by Entity Type",
            "",
            f"*{len(entities)} entities in {len(by_type)} categories*",
            "",
            "---",
            ""
        ]

        # Table of contents
        lines.append("## Contents\n")
        for etype in sorted(by_type.keys()):
            emoji = self._get_type_emoji(etype)
            count = len(by_type[etype])
            lines.append(f"- [{etype.replace('_', ' ').title()}](#{etype}) {emoji} ({count})")
        lines.append("")

        # Each type section
        for etype in sorted(by_type.keys()):
            emoji = self._get_type_emoji(etype)
            lines.append(f"\n## {etype.replace('_', ' ').title()} {emoji} {{#{etype}}}\n")

            # Sort by importance within type
            sorted_entities = sorted(by_type[etype], key=lambda e: e.importance_score, reverse=True)

            for entity in sorted_entities:
                lines.append(f"### {entity.name}")
                lines.append(f"{entity.definition}")
                if entity.aliases:
                    lines.append(f"*Aliases: {', '.join(entity.aliases)}*")
                lines.append("")

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"  Exported by type: {path}")

    def _export_markdown_top(self, entities: list[Entity], path: Path, top_n: int = 100):
        """Export top entities by importance."""
        top_entities = sorted(entities, key=lambda e: e.importance_score, reverse=True)[:top_n]

        lines = [
            f"# Top {len(top_entities)} Key Terms",
            "",
            "*Ranked by frequency and importance*",
            "",
            "---",
            ""
        ]

        for i, entity in enumerate(top_entities, 1):
            emoji = self._get_type_emoji(entity.entity_type)
            lines.append(f"### {i}. {entity.name} {emoji}")
            lines.append("")
            lines.append(f"**{entity.entity_type.replace('_', ' ').title()}** | Score: {entity.importance_score:.2f}")
            lines.append("")
            lines.append(entity.definition)
            lines.append("")
            if entity.source_files:
                sources = entity.source_files[:3]
                lines.append(f"*Found in: {', '.join(sources)}{'...' if len(entity.source_files) > 3 else ''}*")
            lines.append("")

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"  Exported top terms: {path}")

    def _export_stats(self, entities: list[Entity], path: Path):
        """Export extraction statistics."""
        by_type = defaultdict(int)
        for entity in entities:
            by_type[entity.entity_type] += 1

        total_occurrences = sum(e.occurrence_count for e in entities)
        unique_sources = set()
        for entity in entities:
            unique_sources.update(entity.source_files)

        stats = {
            "total_entities": len(entities),
            "total_occurrences": total_occurrences,
            "unique_source_files": len(unique_sources),
            "entities_by_type": dict(by_type),
            "avg_occurrences_per_entity": round(total_occurrences / len(entities), 2) if entities else 0,
            "top_10_by_frequency": [
                {"name": e.name, "type": e.entity_type, "occurrences": e.occurrence_count}
                for e in sorted(entities, key=lambda x: x.occurrence_count, reverse=True)[:10]
            ]
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        print(f"  Exported stats: {path}")

    def _get_type_emoji(self, entity_type: str) -> str:
        """Get emoji for entity type."""
        emojis = {
            "person": "",
            "organization": "",
            "place": "",
            "concept": "",
            "technical_term": "",
            "event": "",
            "work": "",
            "acronym": "",
        }
        return emojis.get(entity_type, "")
