#!/usr/bin/env python3
"""
Upload handler for Substack post archives.

Supports:
- ZIP files containing markdown files
- Direct file paths
- Stdin input for piping
"""

import sys
import zipfile
import shutil
import argparse
from pathlib import Path
from io import BytesIO


def extract_zip(zip_source, output_dir: Path) -> list[Path]:
    """
    Extract markdown files from a ZIP archive.

    Args:
        zip_source: Path to ZIP file, file-like object, or bytes
        output_dir: Directory to extract files to

    Returns:
        List of extracted file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_files = []

    # Handle different input types
    if isinstance(zip_source, (str, Path)):
        zip_file = zipfile.ZipFile(zip_source, 'r')
    elif isinstance(zip_source, bytes):
        zip_file = zipfile.ZipFile(BytesIO(zip_source), 'r')
    else:
        zip_file = zipfile.ZipFile(zip_source, 'r')

    with zip_file:
        for file_info in zip_file.infolist():
            # Skip directories
            if file_info.is_dir():
                continue

            filename = Path(file_info.filename).name
            ext = Path(filename).suffix.lower()

            # Only extract supported file types
            if ext in ['.md', '.markdown', '.html', '.htm', '.json', '.txt']:
                # Extract to flat structure (avoid nested dirs)
                target_path = output_dir / filename

                # Handle duplicates
                if target_path.exists():
                    base = target_path.stem
                    counter = 1
                    while target_path.exists():
                        target_path = output_dir / f"{base}_{counter}{ext}"
                        counter += 1

                # Extract file
                with zip_file.open(file_info) as source:
                    with open(target_path, 'wb') as target:
                        target.write(source.read())

                extracted_files.append(target_path)
                print(f"Extracted: {filename}")

    print(f"\nExtracted {len(extracted_files)} files to {output_dir}")
    return extracted_files


def process_uploaded_zip(zip_path: Path, project_root: Path = None):
    """
    Process an uploaded ZIP file through the full pipeline.

    Args:
        zip_path: Path to the ZIP file
        project_root: Root directory of the project
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent

    raw_data_dir = project_root / "data" / "raw"

    # Clear existing raw data (optional - comment out to accumulate)
    # if raw_data_dir.exists():
    #     shutil.rmtree(raw_data_dir)

    # Extract files
    extracted = extract_zip(zip_path, raw_data_dir)

    if not extracted:
        print("No supported files found in ZIP archive")
        return

    print(f"\nReady to process {len(extracted)} files")
    print(f"Files extracted to: {raw_data_dir}")
    print("\nTo run the pipeline:")
    print(f"  python -m pipeline.main run --input {raw_data_dir}")

    return extracted


def copy_files(source_paths: list[Path], output_dir: Path) -> list[Path]:
    """
    Copy files to the data directory.

    Args:
        source_paths: List of file paths to copy
        output_dir: Directory to copy files to

    Returns:
        List of copied file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []

    for source in source_paths:
        source = Path(source)
        if not source.exists():
            print(f"Warning: {source} does not exist, skipping")
            continue

        target = output_dir / source.name

        # Handle duplicates
        if target.exists():
            base = target.stem
            ext = target.suffix
            counter = 1
            while target.exists():
                target = output_dir / f"{base}_{counter}{ext}"
                counter += 1

        shutil.copy2(source, target)
        copied_files.append(target)
        print(f"Copied: {source.name}")

    print(f"\nCopied {len(copied_files)} files to {output_dir}")
    return copied_files


def main():
    parser = argparse.ArgumentParser(
        description="Upload and extract Substack post archives"
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="ZIP file path or directory containing posts",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output directory (default: data/raw)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read ZIP file from stdin",
    )
    parser.add_argument(
        "--run-pipeline",
        action="store_true",
        help="Run the full pipeline after extraction",
    )

    args = parser.parse_args()

    # Determine project root and output directory
    project_root = Path(__file__).parent.parent
    output_dir = args.output or (project_root / "data" / "raw")

    if args.stdin:
        # Read from stdin
        print("Reading ZIP from stdin...")
        zip_data = sys.stdin.buffer.read()
        extracted = extract_zip(zip_data, output_dir)

    elif args.source:
        source = Path(args.source)

        if source.suffix.lower() == '.zip':
            # Extract ZIP file
            extracted = extract_zip(source, output_dir)
        elif source.is_dir():
            # Copy files from directory
            files = list(source.glob("**/*.md")) + \
                    list(source.glob("**/*.html")) + \
                    list(source.glob("**/*.json"))
            extracted = copy_files(files, output_dir)
        elif source.is_file():
            # Copy single file
            extracted = copy_files([source], output_dir)
        else:
            print(f"Error: {source} is not a valid file or directory")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    # Optionally run pipeline
    if args.run_pipeline and extracted:
        print("\nRunning pipeline...")
        sys.path.insert(0, str(project_root))
        from pipeline.main import SubstackPipeline
        from pipeline.config import default_config

        pipeline = SubstackPipeline(default_config)
        pipeline.run_full_pipeline(output_dir)


if __name__ == "__main__":
    main()
