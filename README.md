# Substack Archive Pipeline

A LangChain-powered pipeline to process hundreds of Substack posts into a searchable archive with AI-generated summaries, glossary, and a static site hosted on GitHub Pages.

## Features

- 📥 **Flexible Import**: Load posts from ZIP files, markdown, HTML, or JSON
- 🔍 **Vector Search**: Semantic search using ChromaDB and sentence embeddings
- 📝 **AI Summaries**: Auto-generated summaries with key points, themes, and concepts
- 📖 **Glossary Extraction**: Automatically extract and define key terms
- 🌐 **Static Site**: GitHub Pages-ready site with search functionality
- 🔄 **Incremental Processing**: Skip already-processed posts

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up API Key

Create a `.env` file with your Anthropic API key:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

### 3. Process Your Posts

**From a ZIP file:**
```bash
python scripts/process_zip.py /path/to/your-posts.zip
```

**From a directory of markdown files:**
```bash
python -m pipeline.main run --input /path/to/posts/
```

### 4. View Your Site

Open `site/index.html` in a browser, or deploy to GitHub Pages.

## Project Structure

```
├── pipeline/              # Core processing modules
│   ├── config.py          # Configuration management
│   ├── loader.py          # Document loaders (MD, HTML, JSON)
│   ├── processor.py       # Text chunking and processing
│   ├── vectorstore.py     # ChromaDB vector storage
│   ├── summarizer.py      # AI summary generation
│   ├── glossary.py        # Term extraction
│   ├── site_generator.py  # Static site builder
│   └── main.py            # Pipeline orchestration
├── scripts/               # Utility scripts
│   ├── process_zip.py     # Quick ZIP processing
│   └── upload_handler.py  # File upload utilities
├── notebooks/             # Jupyter notebooks
├── data/
│   ├── raw/               # Input posts go here
│   └── processed/         # Processed data
├── output/
│   ├── summaries/         # Generated summaries
│   ├── glossary/          # Extracted glossary
│   └── database/          # Vector database
└── site/                  # Generated static site
```

## Usage

### Full Pipeline

```python
from pipeline.main import SubstackPipeline
from pipeline.config import Config

# Initialize
config = Config()
pipeline = SubstackPipeline(config)

# Run everything
pipeline.run_full_pipeline(
    input_dir="data/raw",
    base_url="https://username.github.io/repo"
)
```

### Step by Step

```python
# Load posts
posts = pipeline.load_posts()

# Create vector embeddings
pipeline.process_and_index()

# Generate summaries
summaries = pipeline.generate_summaries()

# Extract glossary
glossary = pipeline.extract_glossary()

# Generate site
pipeline.generate_site(base_url="")
```

### Search Your Archive

```python
# Semantic search
results = pipeline.search("machine learning", k=5)
```

## Configuration

Edit `pipeline/config.py` or create a YAML config file:

```yaml
embedding:
  provider: huggingface  # or openai, ollama
  model_name: all-MiniLM-L6-v2

llm:
  provider: anthropic  # or openai, ollama
  model_name: claude-sonnet-4-20250514
  temperature: 0.3

processing:
  chunk_size: 1000
  chunk_overlap: 200
```

## Supported Input Formats

- **Markdown** (`.md`): With optional YAML frontmatter
- **HTML** (`.html`, `.htm`): Substack export format
- **JSON**: Substack API export format

## Deploy to GitHub Pages

1. Push the `site/` directory to your repository
2. Enable GitHub Pages in repository settings
3. Set source to the `site/` folder

Or use GitHub Actions for automatic deployment.

## Requirements

- Python 3.10+
- Anthropic API key (for summaries/glossary)
- ~500MB disk space for dependencies

## License

MIT
