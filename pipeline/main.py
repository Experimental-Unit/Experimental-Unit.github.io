"""Main orchestration for the Substack processing pipeline."""

import json
import argparse
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

from .config import Config, default_config
from .loader import SubstackLoader, SubstackPost
from .processor import DocumentProcessor
from .vectorstore import VectorStoreManager, SearchIndex
from .summarizer import Summarizer, CollectionSummarizer, PostSummary
from .glossary import GlossaryExtractor, GlossaryTerm
from .site_generator import SiteGenerator


class SubstackPipeline:
    """Main pipeline for processing Substack posts."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.posts: list[SubstackPost] = []
        self.summaries: list[PostSummary] = []
        self.glossary_terms: list[GlossaryTerm] = []

    def load_posts(self, input_dir: Path = None) -> list[SubstackPost]:
        """Load posts from the input directory."""
        input_dir = input_dir or self.config.raw_data_dir
        print(f"Loading posts from {input_dir}...")

        loader = SubstackLoader(input_dir)
        self.posts = loader.load_all()

        print(f"Loaded {len(self.posts)} posts")
        return self.posts

    def process_and_index(self, batch_size: int = 50):
        """Process posts and add to vector store."""
        if not self.posts:
            print("No posts loaded. Run load_posts() first.")
            return

        print("Processing posts for vector store...")

        processor = DocumentProcessor(self.config)
        vectorstore = VectorStoreManager(self.config)

        chunks = processor.process_posts(self.posts)
        print(f"Created {len(chunks)} chunks")

        vectorstore.add_chunks(chunks, batch_size=batch_size)

        stats = vectorstore.get_stats()
        print(f"Vector store now contains {stats['total_documents']} documents")

    def generate_summaries(self, skip_existing: bool = True) -> list[PostSummary]:
        """Generate summaries for all posts."""
        if not self.posts:
            print("No posts loaded. Run load_posts() first.")
            return []

        print("Generating summaries...")

        # Check for existing summaries
        summaries_dir = self.config.output_dir / "summaries"
        existing_ids = set()

        if skip_existing and summaries_dir.exists():
            for f in summaries_dir.glob("*.json"):
                if f.name != "all_summaries.json":
                    existing_ids.add(f.stem)

        posts_to_summarize = [p for p in self.posts if p.id not in existing_ids]

        if existing_ids:
            print(f"Skipping {len(existing_ids)} posts with existing summaries")

        if not posts_to_summarize:
            print("All posts already summarized")
            # Load existing summaries
            return self._load_existing_summaries()

        summarizer = Summarizer(self.config)

        new_summaries = []
        for i, post in enumerate(tqdm(posts_to_summarize, desc="Summarizing")):
            try:
                summary = summarizer.summarize_post(post)
                new_summaries.append(summary)

                # Save immediately
                summary_path = summaries_dir / f"{summary.post_id}.json"
                summaries_dir.mkdir(parents=True, exist_ok=True)
                with open(summary_path, "w") as f:
                    json.dump(summary.to_dict(), f, indent=2)

            except Exception as e:
                print(f"Error summarizing '{post.title}': {e}")

        # Load all summaries (existing + new)
        self.summaries = self._load_existing_summaries()
        print(f"Total summaries: {len(self.summaries)}")

        return self.summaries

    def _load_existing_summaries(self) -> list[PostSummary]:
        """Load existing summaries from disk."""
        summaries_dir = self.config.output_dir / "summaries"
        summaries = []

        if summaries_dir.exists():
            for f in summaries_dir.glob("*.json"):
                if f.name != "all_summaries.json" and f.name != "index.md":
                    with open(f) as file:
                        data = json.load(file)
                        summaries.append(PostSummary.from_dict(data))

        return summaries

    def extract_glossary(self, skip_existing: bool = True) -> list[GlossaryTerm]:
        """Extract glossary terms from all posts."""
        if not self.posts:
            print("No posts loaded. Run load_posts() first.")
            return []

        print("Extracting glossary terms...")

        extractor = GlossaryExtractor(self.config)

        # Load existing glossary if available
        glossary_path = self.config.output_dir / "glossary" / "glossary.json"
        if skip_existing and glossary_path.exists():
            extractor.load(glossary_path)
            print(f"Loaded {len(extractor.terms)} existing terms")

        # Extract from posts
        extractor.extract_from_posts(
            tqdm(self.posts, desc="Extracting terms")
        )

        # Export
        extractor.export(self.config.output_dir / "glossary")

        # Get unique terms
        unique_terms = list({id(t): t for t in extractor.terms.values()}.values())
        self.glossary_terms = unique_terms

        print(f"Total glossary terms: {len(self.glossary_terms)}")
        return self.glossary_terms

    def generate_site(self, base_url: str = ""):
        """Generate the static site."""
        if not self.posts:
            print("No posts loaded. Run load_posts() first.")
            return

        print("Generating static site...")

        # Load summaries if not already loaded
        if not self.summaries:
            self.summaries = self._load_existing_summaries()

        # Load glossary if not already loaded
        if not self.glossary_terms:
            glossary_path = self.config.output_dir / "glossary" / "glossary.json"
            if glossary_path.exists():
                with open(glossary_path) as f:
                    data = json.load(f)
                    self.glossary_terms = [GlossaryTerm.from_dict(t) for t in data]

        generator = SiteGenerator(self.config)
        generator.generate(
            posts=self.posts,
            summaries=self.summaries,
            glossary_terms=self.glossary_terms,
            base_url=base_url,
        )

        print(f"Site generated at {self.config.site_dir}")

    def generate_collection_summary(self) -> str:
        """Generate a high-level summary of the entire collection."""
        if not self.summaries:
            self.summaries = self._load_existing_summaries()

        if not self.summaries:
            print("No summaries available. Run generate_summaries() first.")
            return ""

        print("Generating collection summary...")

        summarizer = CollectionSummarizer(self.config)
        collection_summary = summarizer.summarize_collection(self.summaries)

        # Save
        output_path = self.config.output_dir / "collection_summary.md"
        with open(output_path, "w") as f:
            f.write(collection_summary)

        print(f"Collection summary saved to {output_path}")
        return collection_summary

    def run_full_pipeline(self, input_dir: Path = None, base_url: str = ""):
        """Run the complete pipeline."""
        print("=" * 50)
        print("Starting Substack Processing Pipeline")
        print("=" * 50)

        # 1. Load posts
        self.load_posts(input_dir)

        if not self.posts:
            print("No posts found. Exiting.")
            return

        # 2. Process and index for search
        self.process_and_index()

        # 3. Generate summaries
        self.generate_summaries()

        # 4. Extract glossary
        self.extract_glossary()

        # 5. Generate collection summary
        self.generate_collection_summary()

        # 6. Generate static site
        self.generate_site(base_url)

        print("=" * 50)
        print("Pipeline complete!")
        print(f"Posts processed: {len(self.posts)}")
        print(f"Summaries generated: {len(self.summaries)}")
        print(f"Glossary terms: {len(self.glossary_terms)}")
        print(f"Site available at: {self.config.site_dir}")
        print("=" * 50)

    def search(self, query: str, k: int = 5):
        """Search the vector store."""
        vectorstore = VectorStoreManager(self.config)
        results = vectorstore.search_with_score(query, k=k)

        print(f"\nSearch results for: '{query}'\n")
        for doc, score in results:
            print(f"[{score:.3f}] {doc.metadata.get('title', 'Unknown')}")
            print(f"  {doc.page_content[:200]}...")
            print()

        return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Substack LangChain Pipeline")
    parser.add_argument(
        "command",
        choices=["run", "load", "summarize", "glossary", "site", "search"],
        help="Command to run",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        help="Input directory containing posts",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="",
        help="Base URL for the generated site",
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        help="Search query (for search command)",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        help="Path to config YAML file",
    )

    args = parser.parse_args()

    # Load config
    config = Config.from_yaml(args.config) if args.config else default_config

    # Create pipeline
    pipeline = SubstackPipeline(config)

    if args.command == "run":
        pipeline.run_full_pipeline(args.input, args.base_url)

    elif args.command == "load":
        pipeline.load_posts(args.input)
        print(f"Loaded {len(pipeline.posts)} posts")

    elif args.command == "summarize":
        pipeline.load_posts(args.input)
        pipeline.generate_summaries()

    elif args.command == "glossary":
        pipeline.load_posts(args.input)
        pipeline.extract_glossary()

    elif args.command == "site":
        pipeline.load_posts(args.input)
        pipeline.generate_site(args.base_url)

    elif args.command == "search":
        if not args.query:
            print("Please provide a search query with --query")
            return
        pipeline.search(args.query)


if __name__ == "__main__":
    main()
