"""Configuration management for the pipeline."""

import os
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""

    provider: Literal["openai", "huggingface", "ollama"] = "huggingface"
    model_name: str = "all-MiniLM-L6-v2"  # Default free local model
    # OpenAI: "text-embedding-3-small" or "text-embedding-ada-002"
    # HuggingFace: "all-MiniLM-L6-v2", "all-mpnet-base-v2"


class LLMConfig(BaseModel):
    """LLM configuration for summaries and extraction."""

    provider: Literal["openai", "anthropic", "ollama"] = "anthropic"
    model_name: str = "claude-sonnet-4-20250514"
    # OpenAI: "gpt-4o", "gpt-4o-mini"
    # Anthropic: "claude-sonnet-4-20250514", "claude-3-haiku-20240307"
    # Ollama: "llama3", "mistral"
    temperature: float = 0.3
    max_tokens: int = 4096


class ProcessingConfig(BaseModel):
    """Document processing configuration."""

    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 100


class Config(BaseModel):
    """Main configuration."""

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    raw_data_dir: Path = Field(default="data/raw")
    processed_data_dir: Path = Field(default="data/processed")
    output_dir: Path = Field(default="output")
    site_dir: Path = Field(default="site")

    # Sub-configs
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)

    # Vector store
    vectorstore_path: Path = Field(default="output/database/chroma")
    collection_name: str = "substack_posts"

    # API Keys (loaded from environment)
    openai_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    anthropic_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))

    def __init__(self, **data):
        super().__init__(**data)
        # Resolve relative paths
        self.raw_data_dir = self.project_root / self.raw_data_dir
        self.processed_data_dir = self.project_root / self.processed_data_dir
        self.output_dir = self.project_root / self.output_dir
        self.site_dir = self.project_root / self.site_dir
        self.vectorstore_path = self.project_root / self.vectorstore_path

        # Ensure directories exist
        for path in [self.raw_data_dir, self.processed_data_dir, self.output_dir, self.site_dir]:
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """Load configuration from YAML file."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def save_yaml(self, path: str):
        """Save configuration to YAML file."""
        import yaml
        with open(path, "w") as f:
            yaml.dump(self.model_dump(mode="json"), f, default_flow_style=False)


# Default configuration instance
default_config = Config()
