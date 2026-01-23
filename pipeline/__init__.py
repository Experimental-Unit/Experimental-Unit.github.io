"""
Substack LangChain Pipeline

A comprehensive pipeline for processing Substack posts into:
- Searchable vector database
- AI-generated summaries
- Extracted glossary terms
- Static site for GitHub Pages
"""

from .config import Config
from .loader import SubstackLoader
from .processor import DocumentProcessor
from .vectorstore import VectorStoreManager
from .summarizer import Summarizer
from .glossary import GlossaryExtractor

__version__ = "0.1.0"

__all__ = [
    "Config",
    "SubstackLoader",
    "DocumentProcessor",
    "VectorStoreManager",
    "Summarizer",
    "GlossaryExtractor",
]
