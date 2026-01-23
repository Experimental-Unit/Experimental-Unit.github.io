"""Static site generator for GitHub Pages."""

import json
import shutil
from pathlib import Path
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import Config, default_config
from .loader import SubstackPost
from .summarizer import PostSummary
from .glossary import GlossaryTerm


class SiteGenerator:
    """Generate static HTML site for GitHub Pages."""

    def __init__(self, config: Config = default_config):
        self.config = config
        self.output_dir = config.site_dir
        self.template_dir = config.site_dir / "templates"

        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "posts").mkdir(exist_ok=True)
        (self.output_dir / "static" / "css").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "static" / "js").mkdir(parents=True, exist_ok=True)

        # Setup Jinja2
        self._setup_templates()
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def _setup_templates(self):
        """Create default templates if they don't exist."""
        self.template_dir.mkdir(exist_ok=True)

        # Base template
        base_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Substack Archive{% endblock %}</title>
    <link rel="stylesheet" href="{{ base_url }}/static/css/style.css">
    {% block head %}{% endblock %}
</head>
<body>
    <nav class="navbar">
        <div class="container">
            <a href="{{ base_url }}/" class="logo">📚 Archive</a>
            <ul class="nav-links">
                <li><a href="{{ base_url }}/">Home</a></li>
                <li><a href="{{ base_url }}/summaries.html">Summaries</a></li>
                <li><a href="{{ base_url }}/glossary.html">Glossary</a></li>
                <li><a href="{{ base_url }}/search.html">Search</a></li>
            </ul>
        </div>
    </nav>

    <main class="container">
        {% block content %}{% endblock %}
    </main>

    <footer>
        <div class="container">
            <p>Generated on {{ generated_date }} | Powered by LangChain</p>
        </div>
    </footer>

    {% block scripts %}{% endblock %}
</body>
</html>'''

        # Index template
        index_template = '''{% extends "base.html" %}

{% block title %}Home - Substack Archive{% endblock %}

{% block content %}
<h1>📚 Substack Archive</h1>

<div class="stats">
    <div class="stat-card">
        <span class="stat-number">{{ stats.total_posts }}</span>
        <span class="stat-label">Posts</span>
    </div>
    <div class="stat-card">
        <span class="stat-number">{{ stats.total_words | default(0) | int }}</span>
        <span class="stat-label">Words</span>
    </div>
    <div class="stat-card">
        <span class="stat-number">{{ stats.glossary_terms }}</span>
        <span class="stat-label">Glossary Terms</span>
    </div>
</div>

<section class="recent-posts">
    <h2>Recent Posts</h2>
    {% for post in posts[:10] %}
    <article class="post-card">
        <h3><a href="{{ base_url }}/posts/{{ post.id }}.html">{{ post.title }}</a></h3>
        {% if post.subtitle %}<p class="subtitle">{{ post.subtitle }}</p>{% endif %}
        <p class="meta">
            {% if post.published_date %}{{ post.published_date }}{% endif %}
            · {{ post.word_count }} words
        </p>
    </article>
    {% endfor %}
</section>

<section class="all-posts">
    <h2>All Posts</h2>
    <ul class="post-list">
    {% for post in posts %}
        <li><a href="{{ base_url }}/posts/{{ post.id }}.html">{{ post.title }}</a></li>
    {% endfor %}
    </ul>
</section>
{% endblock %}'''

        # Post template
        post_template = '''{% extends "base.html" %}

{% block title %}{{ post.title }} - Substack Archive{% endblock %}

{% block content %}
<article class="post">
    <header>
        <h1>{{ post.title }}</h1>
        {% if post.subtitle %}<p class="subtitle">{{ post.subtitle }}</p>{% endif %}
        <p class="meta">
            {% if post.author %}By {{ post.author }}{% endif %}
            {% if post.published_date %} · {{ post.published_date }}{% endif %}
            · {{ post.word_count }} words
        </p>
    </header>

    {% if summary %}
    <div class="summary-box">
        <h3>📋 Summary</h3>
        <p><strong>{{ summary.one_liner }}</strong></p>
        <details>
            <summary>Read full summary</summary>
            <p>{{ summary.summary }}</p>
            <h4>Key Points</h4>
            <ul>
            {% for point in summary.key_points %}
                <li>{{ point }}</li>
            {% endfor %}
            </ul>
            <p><strong>Themes:</strong> {{ summary.themes | join(", ") }}</p>
        </details>
    </div>
    {% endif %}

    <div class="content">
        {{ post.content | safe }}
    </div>

    {% if summary and summary.key_concepts %}
    <div class="concepts">
        <h3>Key Concepts</h3>
        <div class="tags">
        {% for concept in summary.key_concepts %}
            <span class="tag">{{ concept }}</span>
        {% endfor %}
        </div>
    </div>
    {% endif %}
</article>
{% endblock %}'''

        # Summaries template
        summaries_template = '''{% extends "base.html" %}

{% block title %}Summaries - Substack Archive{% endblock %}

{% block content %}
<h1>📋 Post Summaries</h1>

<p class="intro">Quick summaries of all {{ summaries | length }} posts in the archive.</p>

{% for summary in summaries %}
<article class="summary-card">
    <h2><a href="{{ base_url }}/posts/{{ summary.post_id }}.html">{{ summary.title }}</a></h2>
    <p class="one-liner">{{ summary.one_liner }}</p>

    <details>
        <summary>View full summary</summary>
        <p>{{ summary.summary }}</p>

        <h4>Key Points</h4>
        <ul>
        {% for point in summary.key_points %}
            <li>{{ point }}</li>
        {% endfor %}
        </ul>

        <p><strong>Themes:</strong> {{ summary.themes | join(", ") }}</p>
        <p><strong>Related Topics:</strong> {{ summary.related_topics | join(", ") }}</p>
    </details>
</article>
{% endfor %}
{% endblock %}'''

        # Glossary template
        glossary_template = '''{% extends "base.html" %}

{% block title %}Glossary - Substack Archive{% endblock %}

{% block content %}
<h1>📖 Glossary</h1>

<p class="intro">{{ terms | length }} terms and concepts from the archive.</p>

<div class="glossary-nav">
    {% for letter in letters %}
    <a href="#{{ letter }}">{{ letter }}</a>
    {% endfor %}
</div>

{% for letter, letter_terms in terms_by_letter.items() %}
<section id="{{ letter }}">
    <h2>{{ letter }}</h2>
    <dl class="glossary-list">
    {% for term in letter_terms %}
        <dt id="term-{{ term.term | lower | replace(' ', '-') }}">{{ term.term }}</dt>
        <dd>
            {{ term.definition }}
            {% if term.aliases %}<br><em>Also: {{ term.aliases | join(", ") }}</em>{% endif %}
            {% if term.related_terms %}<br><strong>Related:</strong> {{ term.related_terms | join(", ") }}{% endif %}
            <span class="term-meta">{{ term.category }} · {{ term.usage_count }} occurrence(s)</span>
        </dd>
    {% endfor %}
    </dl>
</section>
{% endfor %}
{% endblock %}'''

        # Search template
        search_template = '''{% extends "base.html" %}

{% block title %}Search - Substack Archive{% endblock %}

{% block head %}
<script src="https://unpkg.com/lunr/lunr.js"></script>
{% endblock %}

{% block content %}
<h1>🔍 Search</h1>

<div class="search-box">
    <input type="text" id="search-input" placeholder="Search posts..." autofocus>
    <button onclick="performSearch()">Search</button>
</div>

<div id="search-results"></div>
{% endblock %}

{% block scripts %}
<script>
let searchIndex;
let documents;

// Load search index
fetch('{{ base_url }}/static/js/search-index.json')
    .then(r => r.json())
    .then(data => {
        documents = data;
        searchIndex = lunr(function() {
            this.ref('id');
            this.field('title', { boost: 10 });
            this.field('body');
            this.field('tags', { boost: 5 });

            data.forEach(doc => this.add(doc));
        });
    });

function performSearch() {
    const query = document.getElementById('search-input').value;
    if (!query || !searchIndex) return;

    const results = searchIndex.search(query);
    const resultsDiv = document.getElementById('search-results');

    if (results.length === 0) {
        resultsDiv.innerHTML = '<p>No results found.</p>';
        return;
    }

    let html = '<ul class="search-results">';
    results.forEach(result => {
        const doc = documents.find(d => d.id === result.ref);
        if (doc) {
            html += `<li><a href="{{ base_url }}/posts/${doc.id}.html">${doc.title}</a></li>`;
        }
    });
    html += '</ul>';
    resultsDiv.innerHTML = html;
}

document.getElementById('search-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') performSearch();
});
</script>
{% endblock %}'''

        # Write templates
        templates = {
            "base.html": base_template,
            "index.html": index_template,
            "post.html": post_template,
            "summaries.html": summaries_template,
            "glossary.html": glossary_template,
            "search.html": search_template,
        }

        for name, content in templates.items():
            template_path = self.template_dir / name
            if not template_path.exists():
                with open(template_path, "w") as f:
                    f.write(content)

        # Write CSS
        self._write_css()

    def _write_css(self):
        """Write default CSS styles."""
        css = '''/* Modern minimal CSS for Substack Archive */
:root {
    --primary: #0066cc;
    --text: #333;
    --text-light: #666;
    --bg: #fff;
    --bg-alt: #f8f9fa;
    --border: #e0e0e0;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
}

.container {
    max-width: 800px;
    margin: 0 auto;
    padding: 0 20px;
}

/* Navigation */
.navbar {
    background: var(--bg-alt);
    border-bottom: 1px solid var(--border);
    padding: 15px 0;
}

.navbar .container {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.logo {
    font-size: 1.25rem;
    font-weight: bold;
    text-decoration: none;
    color: var(--text);
}

.nav-links {
    list-style: none;
    display: flex;
    gap: 20px;
}

.nav-links a {
    text-decoration: none;
    color: var(--text-light);
}

.nav-links a:hover {
    color: var(--primary);
}

/* Main content */
main {
    padding: 40px 0;
    min-height: calc(100vh - 200px);
}

h1, h2, h3 {
    margin-bottom: 1rem;
}

h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; margin-top: 2rem; }
h3 { font-size: 1.25rem; }

/* Stats */
.stats {
    display: flex;
    gap: 20px;
    margin: 30px 0;
}

.stat-card {
    background: var(--bg-alt);
    padding: 20px;
    border-radius: 8px;
    text-align: center;
    flex: 1;
}

.stat-number {
    display: block;
    font-size: 2rem;
    font-weight: bold;
    color: var(--primary);
}

.stat-label {
    color: var(--text-light);
    font-size: 0.875rem;
}

/* Post cards */
.post-card {
    padding: 20px 0;
    border-bottom: 1px solid var(--border);
}

.post-card h3 a {
    text-decoration: none;
    color: var(--text);
}

.post-card h3 a:hover {
    color: var(--primary);
}

.subtitle {
    color: var(--text-light);
    font-style: italic;
}

.meta {
    color: var(--text-light);
    font-size: 0.875rem;
}

/* Post list */
.post-list {
    columns: 2;
    column-gap: 40px;
}

.post-list li {
    margin-bottom: 8px;
}

.post-list a {
    text-decoration: none;
    color: var(--text);
}

.post-list a:hover {
    color: var(--primary);
}

/* Article */
article.post header {
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
}

.content {
    line-height: 1.8;
}

.content p {
    margin-bottom: 1rem;
}

.content h2, .content h3 {
    margin-top: 2rem;
}

/* Summary box */
.summary-box {
    background: var(--bg-alt);
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 30px;
}

.summary-box details {
    margin-top: 10px;
}

/* Tags */
.tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.tag {
    background: var(--bg-alt);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.875rem;
}

/* Glossary */
.glossary-nav {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 30px;
}

.glossary-nav a {
    display: inline-block;
    width: 30px;
    height: 30px;
    line-height: 30px;
    text-align: center;
    background: var(--bg-alt);
    border-radius: 4px;
    text-decoration: none;
    color: var(--text);
}

.glossary-nav a:hover {
    background: var(--primary);
    color: white;
}

.glossary-list dt {
    font-weight: bold;
    margin-top: 15px;
}

.glossary-list dd {
    margin-left: 20px;
    margin-bottom: 10px;
}

.term-meta {
    display: block;
    font-size: 0.75rem;
    color: var(--text-light);
    margin-top: 5px;
}

/* Search */
.search-box {
    display: flex;
    gap: 10px;
    margin-bottom: 30px;
}

.search-box input {
    flex: 1;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 1rem;
}

.search-box button {
    padding: 12px 24px;
    background: var(--primary);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.search-results li {
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
}

/* Summary cards */
.summary-card {
    padding: 20px 0;
    border-bottom: 1px solid var(--border);
}

.summary-card h2 a {
    text-decoration: none;
    color: var(--text);
}

.one-liner {
    font-style: italic;
    color: var(--text-light);
}

/* Footer */
footer {
    background: var(--bg-alt);
    padding: 20px 0;
    text-align: center;
    color: var(--text-light);
    font-size: 0.875rem;
}

/* Responsive */
@media (max-width: 600px) {
    .stats {
        flex-direction: column;
    }

    .post-list {
        columns: 1;
    }

    .navbar .container {
        flex-direction: column;
        gap: 10px;
    }
}'''

        css_path = self.output_dir / "static" / "css" / "style.css"
        with open(css_path, "w") as f:
            f.write(css)

    def generate(
        self,
        posts: list[SubstackPost],
        summaries: list[PostSummary] = None,
        glossary_terms: list[GlossaryTerm] = None,
        base_url: str = "",
    ):
        """Generate the complete static site."""
        summaries = summaries or []
        glossary_terms = glossary_terms or []

        # Create lookup dicts
        summary_lookup = {s.post_id: s for s in summaries}

        # Common context
        context = {
            "base_url": base_url,
            "generated_date": datetime.now().strftime("%Y-%m-%d"),
        }

        # Generate index
        self._generate_index(posts, summaries, glossary_terms, context)

        # Generate individual post pages
        for post in posts:
            self._generate_post_page(post, summary_lookup.get(post.id), context)

        # Generate summaries page
        if summaries:
            self._generate_summaries_page(summaries, context)

        # Generate glossary page
        if glossary_terms:
            self._generate_glossary_page(glossary_terms, context)

        # Generate search page and index
        self._generate_search(posts, context)

        print(f"Generated site with {len(posts)} posts")

    def _generate_index(self, posts, summaries, glossary_terms, context):
        """Generate the index page."""
        template = self.env.get_template("index.html")

        # Calculate stats
        stats = {
            "total_posts": len(posts),
            "total_words": sum(p.word_count for p in posts),
            "glossary_terms": len(glossary_terms),
        }

        # Sort posts by date (newest first)
        sorted_posts = sorted(
            posts,
            key=lambda p: p.published_date or datetime.min,
            reverse=True,
        )

        # Convert to dicts for template
        post_dicts = []
        for p in sorted_posts:
            post_dicts.append({
                "id": p.id,
                "title": p.title,
                "subtitle": p.subtitle,
                "published_date": p.published_date.strftime("%Y-%m-%d") if p.published_date else None,
                "word_count": p.word_count,
            })

        html = template.render(posts=post_dicts, stats=stats, **context)

        with open(self.output_dir / "index.html", "w") as f:
            f.write(html)

    def _generate_post_page(self, post: SubstackPost, summary: PostSummary, context):
        """Generate a single post page."""
        template = self.env.get_template("post.html")

        # Convert markdown-ish content to HTML (basic)
        import re
        content = post.content
        # Convert markdown headers
        content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
        content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
        # Convert paragraphs
        content = re.sub(r'\n\n+', '</p><p>', content)
        content = f'<p>{content}</p>'

        post_dict = {
            "id": post.id,
            "title": post.title,
            "subtitle": post.subtitle,
            "content": content,
            "author": post.author,
            "published_date": post.published_date.strftime("%Y-%m-%d") if post.published_date else None,
            "word_count": post.word_count,
        }

        summary_dict = None
        if summary:
            summary_dict = {
                "one_liner": summary.one_liner,
                "summary": summary.summary,
                "key_points": summary.key_points,
                "key_concepts": summary.key_concepts,
                "themes": summary.themes,
            }

        html = template.render(post=post_dict, summary=summary_dict, **context)

        with open(self.output_dir / "posts" / f"{post.id}.html", "w") as f:
            f.write(html)

    def _generate_summaries_page(self, summaries: list[PostSummary], context):
        """Generate the summaries page."""
        template = self.env.get_template("summaries.html")

        summary_dicts = [
            {
                "post_id": s.post_id,
                "title": s.title,
                "one_liner": s.one_liner,
                "summary": s.summary,
                "key_points": s.key_points,
                "themes": s.themes,
                "related_topics": s.related_topics,
            }
            for s in summaries
        ]

        html = template.render(summaries=summary_dicts, **context)

        with open(self.output_dir / "summaries.html", "w") as f:
            f.write(html)

    def _generate_glossary_page(self, terms: list[GlossaryTerm], context):
        """Generate the glossary page."""
        template = self.env.get_template("glossary.html")

        # Sort terms alphabetically
        sorted_terms = sorted(terms, key=lambda t: t.term.lower())

        # Group by first letter
        terms_by_letter = {}
        for term in sorted_terms:
            letter = term.term[0].upper()
            if letter not in terms_by_letter:
                terms_by_letter[letter] = []
            terms_by_letter[letter].append({
                "term": term.term,
                "definition": term.definition,
                "category": term.category,
                "aliases": term.aliases,
                "related_terms": term.related_terms,
                "usage_count": term.usage_count,
            })

        letters = sorted(terms_by_letter.keys())

        html = template.render(
            terms=sorted_terms,
            terms_by_letter=terms_by_letter,
            letters=letters,
            **context,
        )

        with open(self.output_dir / "glossary.html", "w") as f:
            f.write(html)

    def _generate_search(self, posts: list[SubstackPost], context):
        """Generate search page and index."""
        # Search page
        template = self.env.get_template("search.html")
        html = template.render(**context)

        with open(self.output_dir / "search.html", "w") as f:
            f.write(html)

        # Search index for Lunr.js
        search_docs = []
        for post in posts:
            search_docs.append({
                "id": post.id,
                "title": post.title,
                "body": post.content[:2000] if post.content else "",
                "tags": " ".join(post.tags),
            })

        js_dir = self.output_dir / "static" / "js"
        js_dir.mkdir(exist_ok=True)

        with open(js_dir / "search-index.json", "w") as f:
            json.dump(search_docs, f)
