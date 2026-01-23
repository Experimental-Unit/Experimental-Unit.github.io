#!/usr/bin/env python3
"""
Quick script to process a ZIP file of Substack posts.

Usage:
    python scripts/process_zip.py /path/to/posts.zip

This will:
1. Extract the ZIP to data/raw/
2. Run the full processing pipeline
3. Generate the static site
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.upload_handler import extract_zip
from pipeline.main import SubstackPipeline
from pipeline.config import Config


def process_zip(zip_path: str, base_url: str = ""):
    """Process a ZIP file through the complete pipeline."""

    zip_path = Path(zip_path)
    if not zip_path.exists():
        print(f"Error: ZIP file not found: {zip_path}")
        sys.exit(1)

    # Setup directories
    raw_data_dir = project_root / "data" / "raw"

    print("=" * 50)
    print("Substack Archive Processor")
    print("=" * 50)

    # Step 1: Extract ZIP
    print(f"\n[1/2] Extracting {zip_path.name}...")
    extracted = extract_zip(zip_path, raw_data_dir)

    if not extracted:
        print("No supported files found in ZIP")
        sys.exit(1)

    # Step 2: Run pipeline
    print("\n[2/2] Running processing pipeline...")
    config = Config()
    pipeline = SubstackPipeline(config)
    pipeline.run_full_pipeline(raw_data_dir, base_url)

    print("\n" + "=" * 50)
    print("Processing complete!")
    print(f"Site generated at: {config.site_dir}")
    print("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/process_zip.py /path/to/posts.zip [base_url]")
        print("\nExample:")
        print("  python scripts/process_zip.py ~/Downloads/my-substack-posts.zip")
        print("  python scripts/process_zip.py posts.zip https://username.github.io")
        sys.exit(1)

    zip_file = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else ""

    process_zip(zip_file, base_url)
