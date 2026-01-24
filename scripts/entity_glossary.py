#!/usr/bin/env python3
"""
Entity Extraction & Glossary Builder

A powerful tool to extract entities from large volumes of text and build
comprehensive glossaries.

Supports:
- ZIP files containing .txt and .md files
- Individual .txt files
- Individual .md files
- Directories of text files
- Nested ZIP files

Usage:
    python scripts/entity_glossary.py /path/to/documents.zip
    python scripts/entity_glossary.py /path/to/file.txt /path/to/file2.md
    python scripts/entity_glossary.py /path/to/folder/
    python scripts/entity_glossary.py *.md --output ./my-glossary

Features:
    - Extracts 8 entity types: people, organizations, places, concepts,
      technical terms, events, works, and acronyms
    - Merges and deduplicates entities across all files
    - Calculates importance scores based on frequency
    - Exports to JSON and multiple Markdown formats
    - Progress tracking with rich terminal output
"""

import sys
import argparse
import zipfile
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pipeline.entity_extractor import EntityExtractor, GlossaryBuilder
from pipeline.config import Config


# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def print_header():
    """Print the tool header."""
    print(f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════╗
║          Entity Extraction & Glossary Builder            ║
║                                                          ║
║   Extract entities from text and build glossaries        ║
╚══════════════════════════════════════════════════════════╝{Colors.ENDC}
""")


def print_section(title: str):
    """Print a section header."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}▶ {title}{Colors.ENDC}")
    print(f"{Colors.DIM}{'─' * 50}{Colors.ENDC}")


def print_success(message: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.ENDC}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.ENDC}")


def print_info(message: str):
    """Print an info message."""
    print(f"{Colors.CYAN}ℹ {message}{Colors.ENDC}")


def extract_zip(zip_path: Path, output_dir: Path) -> list[Path]:
    """
    Extract supported files from a ZIP archive.

    Handles nested ZIPs by extracting them recursively.
    """
    extracted_files = []

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for file_info in zf.infolist():
            if file_info.is_dir():
                continue

            filename = Path(file_info.filename).name
            ext = Path(filename).suffix.lower()

            # Handle supported text formats
            if ext in ['.txt', '.md', '.markdown']:
                target_path = output_dir / filename

                # Handle duplicates
                if target_path.exists():
                    base = target_path.stem
                    counter = 1
                    while target_path.exists():
                        target_path = output_dir / f"{base}_{counter}{ext}"
                        counter += 1

                with zf.open(file_info) as source:
                    with open(target_path, 'wb') as target:
                        target.write(source.read())

                extracted_files.append(target_path)

            # Handle nested ZIPs
            elif ext == '.zip':
                nested_zip_path = output_dir / f"_nested_{filename}"
                with zf.open(file_info) as source:
                    with open(nested_zip_path, 'wb') as target:
                        target.write(source.read())

                # Recursively extract
                nested_files = extract_zip(nested_zip_path, output_dir)
                extracted_files.extend(nested_files)

                # Clean up nested zip
                nested_zip_path.unlink()

    return extracted_files


def collect_files(sources: list[str]) -> list[Path]:
    """
    Collect all supported files from the given sources.

    Sources can be:
    - ZIP files
    - Individual text/markdown files
    - Directories
    """
    all_files = []
    temp_dirs = []

    for source in sources:
        path = Path(source)

        if not path.exists():
            print_warning(f"Path not found: {source}")
            continue

        if path.suffix.lower() == '.zip':
            # Extract ZIP to temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix="entity_extract_"))
            temp_dirs.append(temp_dir)

            print_info(f"Extracting: {path.name}")
            extracted = extract_zip(path, temp_dir)
            all_files.extend(extracted)
            print_success(f"Extracted {len(extracted)} files from {path.name}")

        elif path.suffix.lower() in ['.txt', '.md', '.markdown']:
            all_files.append(path)

        elif path.is_dir():
            # Recursively find all supported files
            for ext in ['*.txt', '*.md', '*.markdown']:
                found = list(path.rglob(ext))
                all_files.extend(found)

            # Also check for ZIPs in directory
            for zip_file in path.rglob('*.zip'):
                temp_dir = Path(tempfile.mkdtemp(prefix="entity_extract_"))
                temp_dirs.append(temp_dir)
                print_info(f"Extracting nested: {zip_file.name}")
                extracted = extract_zip(zip_file, temp_dir)
                all_files.extend(extracted)

    return all_files, temp_dirs


def create_progress_callback():
    """Create a progress callback with rich output."""
    start_time = datetime.now()

    def callback(current: int, total: int, filename: str, entity_count: int):
        elapsed = (datetime.now() - start_time).total_seconds()
        rate = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / rate if rate > 0 else 0

        # Progress bar
        bar_width = 30
        filled = int(bar_width * current / total)
        bar = '█' * filled + '░' * (bar_width - filled)

        # Status line
        status = f"\r{Colors.CYAN}[{bar}]{Colors.ENDC} {current}/{total} "
        status += f"│ {filename[:30]:<30} │ {entity_count:>3} entities "
        status += f"│ ETA: {int(eta)}s"

        print(status, end='', flush=True)

        if current == total:
            print()  # New line when done

    return callback


def main():
    parser = argparse.ArgumentParser(
        description="Extract entities from text files and build a comprehensive glossary.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process a ZIP file
    python scripts/entity_glossary.py documents.zip

    # Process multiple files
    python scripts/entity_glossary.py notes.txt research.md paper.md

    # Process a directory
    python scripts/entity_glossary.py ./my-documents/

    # Specify custom output directory
    python scripts/entity_glossary.py data.zip --output ./glossary-output

    # Use a different model
    python scripts/entity_glossary.py data.zip --model claude-3-haiku-20240307
        """
    )

    parser.add_argument(
        "sources",
        nargs="+",
        help="ZIP files, text files (.txt, .md), or directories to process"
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output directory for glossary files (default: ./entity_glossary_output)"
    )

    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="LLM model to use (default: from config.yaml)"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=8000,
        help="Maximum chunk size for processing (default: 8000)"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output (no progress bars)"
    )

    args = parser.parse_args()

    # Print header
    if not args.quiet:
        print_header()

    # Setup output directory
    output_dir = args.output or Path("./entity_glossary_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect files
    print_section("Collecting Files")
    all_files, temp_dirs = collect_files(args.sources)

    if not all_files:
        print_error("No supported files found (.txt, .md, .markdown)")
        sys.exit(1)

    print_success(f"Found {len(all_files)} files to process")

    # Show file breakdown
    txt_count = sum(1 for f in all_files if f.suffix.lower() == '.txt')
    md_count = sum(1 for f in all_files if f.suffix.lower() in ['.md', '.markdown'])
    print(f"   {Colors.DIM}├── {txt_count} text files{Colors.ENDC}")
    print(f"   {Colors.DIM}└── {md_count} markdown files{Colors.ENDC}")

    # Calculate total text size
    total_chars = sum(f.stat().st_size for f in all_files)
    print_info(f"Total text: ~{total_chars:,} characters ({total_chars / 1_000_000:.1f} MB)")

    # Initialize extractor
    print_section("Initializing Entity Extractor")

    config = Config()
    if args.model:
        config.llm.model_name = args.model

    print_info(f"Using model: {config.llm.model_name}")
    print_info(f"Provider: {config.llm.provider}")

    extractor = EntityExtractor(config)
    print_success("Extractor initialized")

    # Process files
    print_section("Extracting Entities")
    print_info("This may take a while for large text volumes...")
    print()

    callback = create_progress_callback() if not args.quiet else None

    try:
        entities = extractor.process_files(all_files, progress_callback=callback)
    except KeyboardInterrupt:
        print()
        print_warning("Processing interrupted by user")
        entities = extractor.entities

    # Show extraction summary
    unique_entities = extractor.get_unique_entities()
    print()
    print_success(f"Extracted {len(unique_entities)} unique entities")

    # Show breakdown by type
    type_counts = {}
    for entity in unique_entities:
        type_counts[entity.entity_type] = type_counts.get(entity.entity_type, 0) + 1

    print()
    print(f"{Colors.BOLD}Entities by type:{Colors.ENDC}")
    for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        bar = '▓' * min(count // 2, 30)
        print(f"   {etype:20} {Colors.CYAN}{bar}{Colors.ENDC} {count}")

    # Build and export glossary
    print_section("Building Glossary")

    builder = GlossaryBuilder(entities)
    exported_count = builder.export_all(output_dir)

    print()
    print_success(f"Exported {exported_count} entities to {output_dir}")

    # Show output files
    print()
    print(f"{Colors.BOLD}Output files:{Colors.ENDC}")
    for f in sorted(output_dir.iterdir()):
        size = f.stat().st_size
        if size > 1024 * 1024:
            size_str = f"{size / 1024 / 1024:.1f} MB"
        elif size > 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size} bytes"
        print(f"   {Colors.DIM}├── {f.name} ({size_str}){Colors.ENDC}")

    # Cleanup temp directories
    for temp_dir in temp_dirs:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Final summary
    print()
    print(f"{Colors.GREEN}{Colors.BOLD}╔══════════════════════════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.GREEN}{Colors.BOLD}║                    Processing Complete                    ║{Colors.ENDC}")
    print(f"{Colors.GREEN}{Colors.BOLD}╚══════════════════════════════════════════════════════════╝{Colors.ENDC}")
    print()
    print(f"   Files processed:    {len(all_files)}")
    print(f"   Entities extracted: {len(unique_entities)}")
    print(f"   Output directory:   {output_dir.absolute()}")
    print()
    print(f"   {Colors.CYAN}View your glossary:{Colors.ENDC}")
    print(f"   cat {output_dir / 'glossary.md'}")
    print()


if __name__ == "__main__":
    main()
