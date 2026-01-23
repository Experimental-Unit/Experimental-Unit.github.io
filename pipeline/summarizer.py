"""Summary generation using LLMs."""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

from .config import Config, default_config
from .loader import SubstackPost


def get_llm(config: Config):
    """Get LLM based on configuration."""
    provider = config.llm.provider
    model_name = config.llm.model_name

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            anthropic_api_key=config.anthropic_api_key,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            openai_api_key=config.openai_api_key,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
    elif provider == "ollama":
        from langchain_community.llms import Ollama

        return Ollama(model=model_name, temperature=config.llm.temperature)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


@dataclass
class PostSummary:
    """Summary of a single post."""

    post_id: str
    title: str
    one_liner: str  # Single sentence summary
    summary: str  # 2-3 paragraph summary
    key_points: list[str]  # Bullet points
    key_concepts: list[str]  # Important terms/concepts mentioned
    themes: list[str]  # High-level themes
    related_topics: list[str]  # Topics for cross-referencing

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PostSummary":
        return cls(**data)


class Summarizer:
    """Generate summaries for Substack posts."""

    def __init__(self, config: Config = default_config):
        self.config = config
        self.llm = get_llm(config)

        # Summary prompt
        self.summary_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert at analyzing and summarizing written content.
Your task is to create comprehensive summaries that capture the essence of each piece.
Always be accurate to the source material and identify the key insights.""",
                ),
                (
                    "human",
                    """Analyze this post and provide a structured summary.

Title: {title}
{subtitle}

Content:
{content}

Provide your response as JSON with this structure:
{{
    "one_liner": "A single sentence capturing the main point",
    "summary": "A 2-3 paragraph comprehensive summary",
    "key_points": ["Point 1", "Point 2", "Point 3", ...],
    "key_concepts": ["Concept 1", "Concept 2", ...],
    "themes": ["Theme 1", "Theme 2", ...],
    "related_topics": ["Topic 1", "Topic 2", ...]
}}

Ensure key_points has 3-7 items, key_concepts has 3-10 items, themes has 2-5 items, and related_topics has 3-8 items.""",
                ),
            ]
        )

        self.chain = self.summary_prompt | self.llm | StrOutputParser()

    def summarize_post(self, post: SubstackPost) -> PostSummary:
        """Generate a summary for a single post."""
        # Truncate content if too long (keep most important parts)
        content = post.content
        if len(content) > 15000:
            # Keep beginning and end
            content = content[:10000] + "\n\n[...content truncated...]\n\n" + content[-5000:]

        subtitle = f"Subtitle: {post.subtitle}" if post.subtitle else ""

        response = self.chain.invoke(
            {
                "title": post.title,
                "subtitle": subtitle,
                "content": content,
            }
        )

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            data = {
                "one_liner": post.title,
                "summary": response[:1000],
                "key_points": [],
                "key_concepts": [],
                "themes": [],
                "related_topics": [],
            }

        return PostSummary(
            post_id=post.id,
            title=post.title,
            one_liner=data.get("one_liner", ""),
            summary=data.get("summary", ""),
            key_points=data.get("key_points", []),
            key_concepts=data.get("key_concepts", []),
            themes=data.get("themes", []),
            related_topics=data.get("related_topics", []),
        )

    def summarize_posts(
        self, posts: list[SubstackPost], progress_callback=None
    ) -> list[PostSummary]:
        """Generate summaries for multiple posts."""
        summaries = []
        total = len(posts)

        for i, post in enumerate(posts):
            try:
                summary = self.summarize_post(post)
                summaries.append(summary)

                if progress_callback:
                    progress_callback(i + 1, total, post.title)
                else:
                    print(f"[{i + 1}/{total}] Summarized: {post.title}")

            except Exception as e:
                print(f"Error summarizing '{post.title}': {e}")

        return summaries

    def export_summaries(self, summaries: list[PostSummary], output_dir: Path):
        """Export summaries to files."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Individual summary files
        for summary in summaries:
            file_path = output_dir / f"{summary.post_id}.json"
            with open(file_path, "w") as f:
                json.dump(summary.to_dict(), f, indent=2)

        # Combined summaries file
        all_summaries = [s.to_dict() for s in summaries]
        with open(output_dir / "all_summaries.json", "w") as f:
            json.dump(all_summaries, f, indent=2)

        # Markdown summary index
        self._export_markdown_index(summaries, output_dir / "index.md")

    def _export_markdown_index(self, summaries: list[PostSummary], output_path: Path):
        """Create a markdown index of all summaries."""
        lines = ["# Post Summaries\n"]

        for summary in summaries:
            lines.append(f"## {summary.title}\n")
            lines.append(f"*{summary.one_liner}*\n")
            lines.append(f"\n{summary.summary}\n")
            lines.append("\n**Key Points:**")
            for point in summary.key_points:
                lines.append(f"- {point}")
            lines.append("\n**Themes:** " + ", ".join(summary.themes))
            lines.append("\n---\n")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))


class CollectionSummarizer:
    """Generate high-level summaries across multiple posts."""

    def __init__(self, config: Config = default_config):
        self.config = config
        self.llm = get_llm(config)

        self.collection_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert at synthesizing information across multiple documents.
Your task is to identify overarching themes, patterns, and insights across a collection of posts.""",
                ),
                (
                    "human",
                    """Here are summaries of {count} posts from a Substack publication:

{summaries}

Create a comprehensive overview that includes:
1. Main themes and topics covered across the collection
2. Key recurring concepts and ideas
3. Evolution of thought or narrative arcs
4. Unique insights or perspectives offered
5. Suggested reading paths (e.g., "Start with X if interested in Y")

Format as markdown.""",
                ),
            ]
        )

    def summarize_collection(self, summaries: list[PostSummary]) -> str:
        """Generate a collection-wide summary."""
        # Format individual summaries
        summary_texts = []
        for s in summaries:
            text = f"**{s.title}**: {s.one_liner}\nThemes: {', '.join(s.themes)}"
            summary_texts.append(text)

        chain = self.collection_prompt | self.llm | StrOutputParser()

        return chain.invoke(
            {
                "count": len(summaries),
                "summaries": "\n\n".join(summary_texts),
            }
        )
