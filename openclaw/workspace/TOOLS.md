# Custom Tools Documentation

## Substack Pipeline Tools

These tools integrate OpenClaw with the Substack archive processing pipeline.

### substack.load

Load Substack posts from a directory.

**Parameters:**
- `input_dir` (string, optional): Path to input directory. Defaults to `data/raw`
- `formats` (array, optional): File formats to load. Defaults to `["md", "html", "json"]`

**Returns:** Array of loaded posts with metadata

**Example:**
```
substack.load --input_dir="./data/raw"
```

---

### substack.process

Process loaded posts into chunks for vector embedding.

**Parameters:**
- `chunk_size` (number, optional): Size of text chunks. Defaults to 1000
- `chunk_overlap` (number, optional): Overlap between chunks. Defaults to 200

**Returns:** Processing statistics and chunk count

**Example:**
```
substack.process --chunk_size=1000 --chunk_overlap=200
```

---

### substack.summarize

Generate AI summaries for processed posts.

**Parameters:**
- `model` (string, optional): LLM model to use. Defaults to config value
- `max_posts` (number, optional): Maximum posts to summarize. Defaults to all

**Returns:** Summary statistics and paths to generated summaries

**Example:**
```
substack.summarize --max_posts=10
```

---

### substack.glossary

Extract glossary terms from posts.

**Parameters:**
- `min_occurrences` (number, optional): Minimum term occurrences. Defaults to 2
- `categories` (array, optional): Term categories to extract

**Returns:** Extracted glossary terms with definitions

**Example:**
```
substack.glossary --min_occurrences=3
```

---

### substack.entities

Extract named entities from posts.

**Parameters:**
- `entity_types` (array, optional): Types to extract. Defaults to all types
  - Available: `people`, `organizations`, `places`, `concepts`, `technical`, `events`, `works`, `acronyms`

**Returns:** Extracted entities with metadata

**Example:**
```
substack.entities --entity_types=["people", "organizations", "concepts"]
```

---

### substack.search

Perform semantic search across the archive.

**Parameters:**
- `query` (string, required): Search query
- `top_k` (number, optional): Number of results. Defaults to 5
- `filter` (object, optional): Metadata filters

**Returns:** Relevant documents with similarity scores

**Example:**
```
substack.search --query="machine learning applications" --top_k=10
```

---

### substack.generate-site

Generate static site for GitHub Pages.

**Parameters:**
- `output_dir` (string, optional): Output directory. Defaults to `site`
- `theme` (string, optional): Site theme. Defaults to `default`

**Returns:** Generated site statistics and path

**Example:**
```
substack.generate-site --output_dir="./site"
```

---

## Git Tools

Standard git operations with GitHub integration.

### git.status

Get current git status.

### git.add

Stage files for commit.

**Parameters:**
- `files` (array, required): Files to stage

### git.commit

Create a commit.

**Parameters:**
- `message` (string, required): Commit message

### git.push

Push to remote.

**Parameters:**
- `branch` (string, optional): Branch name
- `force` (boolean, optional): Force push. Defaults to false

### git.branch

Create or switch branches.

**Parameters:**
- `name` (string, required): Branch name
- `create` (boolean, optional): Create new branch

### git.pr

Create a pull request.

**Parameters:**
- `title` (string, required): PR title
- `body` (string, optional): PR description
- `base` (string, optional): Base branch. Defaults to main
