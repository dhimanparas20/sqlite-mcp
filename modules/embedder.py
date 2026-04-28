"""Document embedder module — loads files/URLs, chunks, embeds, and stores to ChromaDB."""

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import chromadb
from langchain_chroma import Chroma

from modules.logger import get_logger

logger = get_logger("Embedder")

CHROMA_DIR = os.getenv("CHROMA_DIR", "./datastore/internal/chroma")


# ---------------------------------------------------------------------------
# Embedding provider registry (mirrors agent_utils.py pattern)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmbeddingConfig:
    module_name: str
    class_name: str
    model_env: str
    api_key_env: str
    base_url_env: str = ""


EMBEDDING_REGISTRY: dict[str, EmbeddingConfig] = {
    "openai": EmbeddingConfig(
        module_name="langchain_openai",
        class_name="OpenAIEmbeddings",
        model_env="OPENAI_EMBEDDINGS_MODEL",
        api_key_env="OPENAI_API_KEY",
    ),
    "google": EmbeddingConfig(
        module_name="langchain_google_genai",
        class_name="GoogleGenerativeAIEmbeddings",
        model_env="GOOGLE_EMBEDDINGS_MODEL",
        api_key_env="GOOGLE_API_KEY",
    ),
    "openrouter": EmbeddingConfig(
        module_name="langchain_openai",
        class_name="OpenAIEmbeddings",
        model_env="OPEN_ROUTER_EMBEDDINGS_MODEL",
        api_key_env="OPEN_ROUTER_API_KEY",
        base_url_env="OPEN_ROUTER_BASE_URL",
    ),
    "nvidia": EmbeddingConfig(
        module_name="langchain_nvidia_ai_endpoints",
        class_name="NVIDIAEmbeddings",
        model_env="NVIDIA_EMBEDDINGS_MODEL",
        api_key_env="NVIDIA_API_KEY",
    ),
}


def create_embeddings(
    model_name: str | None = None,
    api_key: str | None = None,
    provider: Literal["openai", "google", "openrouter", "nvidia"] = "openai",
):
    """Factory function to create a LangChain embeddings instance.

    Follows the same pattern as ``create_llm`` in agent_utils.py.
    """
    config = EMBEDDING_REGISTRY.get(provider)
    if not config:
        raise ValueError(f"Unknown embedding provider: '{provider}'. " f"Supported: {list(EMBEDDING_REGISTRY.keys())}")

    resolved_model = model_name or os.getenv(config.model_env)
    resolved_key = api_key or os.getenv(config.api_key_env)

    if not resolved_model:
        raise ValueError(f"No model provided and env var '{config.model_env}' is not set.")
    if not resolved_key:
        raise ValueError(f"No API key provided and env var '{config.api_key_env}' is not set.")

    logger.info("📐 Loading %s embeddings: %s", provider, resolved_model)

    try:
        module = importlib.import_module(config.module_name)
        EmbClass = getattr(module, config.class_name)
    except (ImportError, AttributeError) as exc:
        raise ImportError(
            f"Could not load '{config.class_name}' from '{config.module_name}'. "
            f"Is the package installed? Error: {exc}"
        ) from exc

    kwargs: dict = {"model": resolved_model, "api_key": resolved_key}

    if config.base_url_env:
        base_url = os.getenv(config.base_url_env)
        if base_url:
            kwargs["base_url"] = base_url

    return EmbClass(**kwargs)


# ---------------------------------------------------------------------------
# Document loaders — returns list[Document]
# ---------------------------------------------------------------------------


def _is_url(source: str) -> bool:
    """Check if a string is a URL."""
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https")


def _load_file(path: Path):
    """Load a single file and return a list of LangChain Documents."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        from langchain_community.document_loaders import PyPDFLoader

        return PyPDFLoader(str(path)).load()

    if suffix in (".md", ".markdown"):
        from langchain_community.document_loaders import UnstructuredMarkdownLoader

        return UnstructuredMarkdownLoader(str(path)).load()

    if suffix == ".csv":
        from langchain_community.document_loaders import CSVLoader

        return CSVLoader(str(path)).load()

    if suffix == ".txt":
        from langchain_community.document_loaders import TextLoader

        return TextLoader(str(path)).load()

    if suffix == ".json":
        from langchain_community.document_loaders import JSONLoader

        return JSONLoader(str(path), jq_schema=".", text_content=False).load()

    if suffix in (".docx", ".doc"):
        from langchain_community.document_loaders import Docx2txtLoader

        return Docx2txtLoader(str(path)).load()

    if suffix == ".html" or suffix == ".htm":
        from langchain_community.document_loaders import UnstructuredHTMLLoader

        return UnstructuredHTMLLoader(str(path)).load()

    if suffix == ".xml":
        from langchain_community.document_loaders import UnstructuredXMLLoader

        return UnstructuredXMLLoader(str(path)).load()

    # Fallback — try plain text
    from langchain_community.document_loaders import TextLoader

    return TextLoader(str(path)).load()


def _load_url(url: str):
    """Load content from a URL and return a list of LangChain Documents."""
    from langchain_community.document_loaders import WebBaseLoader

    return WebBaseLoader(url).load()


def load_documents(source: str | list[str]) -> list:
    """Load documents from file paths or URLs.

    Args:
        source: A single path/URL string or a list of them.

    Returns:
        Flat list of LangChain Document objects.
    """
    if isinstance(source, str):
        source = [source]

    docs = []
    for item in source:
        try:
            if _is_url(item):
                docs.extend(_load_url(item))
                logger.info("🌐 Loaded URL: %s", item)
            else:
                path = Path(item).resolve()
                if not path.exists():
                    logger.warning("⚠️  File not found: %s", path)
                    continue
                docs.extend(_load_file(path))
                logger.info("📄 Loaded file: %s (%d docs)", path, len(docs))
        except Exception as exc:
            logger.error("❌ Failed to load '%s': %s", item, exc)

    return docs


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def chunk_documents(
    docs: list,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list:
    """Split documents into chunks using RecursiveCharacterTextSplitter."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    logger.info("✂️  Chunked %d docs → %d chunks", len(docs), len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Embed & store
# ---------------------------------------------------------------------------


def embed_and_store(
    source: str | list[str],
    collection_name: str = "default",
    provider: Literal["openai", "google", "openrouter", "nvidia"] | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    chroma_dir: str | None = None,
) -> dict:
    """Load → chunk → embed → store documents in ChromaDB.

    Args:
        source: File path(s) or URL(s) to embed.
        collection_name: ChromaDB collection name (default: "default").
        provider: Embedding provider. Falls back to EMBEDDING_PROVIDER env var.
        model_name: Embedding model override.
        api_key: API key override.
        chunk_size: Text chunk size.
        chunk_overlap: Overlap between chunks.
        chroma_dir: Custom ChromaDB persist directory.

    Returns:
        Dict with status, chunk count, and collection name.
    """

    provider = provider or os.getenv("EMBEDDING_PROVIDER", "openai")
    persist_dir = chroma_dir or CHROMA_DIR
    Path(persist_dir).mkdir(parents=True, exist_ok=True)

    # 1. Load documents
    docs = load_documents(source)
    if not docs:
        return {"ok": False, "error": "No documents loaded", "chunks": 0}

    # 2. Chunk
    chunks = chunk_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        return {"ok": False, "error": "Chunking produced no results", "chunks": 0}

    # 3. Create embeddings
    embeddings = create_embeddings(model_name=model_name, api_key=api_key, provider=provider)

    # 4. Store in ChromaDB
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=persist_dir,
    )

    logger.info(
        "💾 Stored %d chunks in ChromaDB collection '%s' @ %s",
        len(chunks),
        collection_name,
        persist_dir,
    )

    return {
        "ok": True,
        "chunks": len(chunks),
        "collection": collection_name,
        "persist_dir": persist_dir,
    }


# ---------------------------------------------------------------------------
# Query / retrieve
# ---------------------------------------------------------------------------


def query_documents(
    query: str,
    collection_name: str = "default",
    provider: Literal["openai", "google", "openrouter", "nvidia"] | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    chroma_dir: str | None = None,
    k: int = 4,
) -> dict:
    """Query the ChromaDB vector store and return matching documents.

    Args:
        query: The search query string.
        collection_name: ChromaDB collection to search.
        provider: Embedding provider. Falls back to EMBEDDING_PROVIDER env var.
        model_name: Embedding model override.
        api_key: API key override.
        chroma_dir: Custom ChromaDB persist directory.
        k: Number of results to return (default: 4).

    Returns:
        Dict with status and list of matching document contents + metadata.
    """
    provider = provider or os.getenv("EMBEDDING_PROVIDER", "openai")
    persist_dir = chroma_dir or CHROMA_DIR

    if not Path(persist_dir).exists():
        return {"ok": False, "error": f"ChromaDB directory not found: {persist_dir}", "results": []}

    embeddings = create_embeddings(model_name=model_name, api_key=api_key, provider=provider)

    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )

    results = vectordb.similarity_search(query, k=k)

    return {
        "ok": True,
        "query": query,
        "collection": collection_name,
        "results": [{"content": doc.page_content, "metadata": doc.metadata} for doc in results],
    }


# ---------------------------------------------------------------------------
# ChromaDB management
# ---------------------------------------------------------------------------


def list_collections(
    chroma_dir: str | None = None,
) -> dict:
    """List all collections in ChromaDB.

    Returns:
        Dict with list of collection names and their item counts.
    """
    persist_dir = chroma_dir or CHROMA_DIR
    if not Path(persist_dir).exists():
        return {"ok": True, "collections": [], "count": 0}

    client = chromadb.PersistentClient(path=persist_dir)
    collections = client.list_collections()

    result = []
    for col in collections:
        result.append({"name": col.name, "count": col.count()})

    return {"ok": True, "collections": result, "count": len(result)}


def clear_collection(
    collection_name: str = "default",
    chroma_dir: str | None = None,
) -> dict:
    """Delete all documents from a ChromaDB collection without removing the collection.

    Args:
        collection_name: Name of the collection to clear.
        chroma_dir: Custom ChromaDB persist directory.

    Returns:
        Dict with status and number of items deleted.
    """
    persist_dir = chroma_dir or CHROMA_DIR
    if not Path(persist_dir).exists():
        return {"ok": False, "error": f"ChromaDB directory not found: {persist_dir}"}

    client = chromadb.PersistentClient(path=persist_dir)

    try:
        col = client.get_collection(collection_name)
    except Exception:
        return {"ok": False, "error": f"Collection '{collection_name}' not found"}

    count = col.count()
    if count == 0:
        return {"ok": True, "collection": collection_name, "deleted": 0}

    # Get all IDs and delete them
    all_ids = col.get()["ids"]
    if all_ids:
        col.delete(ids=all_ids)

    logger.info("🗑️  Cleared %d items from collection '%s'", count, collection_name)
    return {"ok": True, "collection": collection_name, "deleted": count}


def delete_collection(
    collection_name: str = "default",
    chroma_dir: str | None = None,
) -> dict:
    """Delete an entire ChromaDB collection.

    Args:
        collection_name: Name of the collection to delete.
        chroma_dir: Custom ChromaDB persist directory.

    Returns:
        Dict with status.
    """
    persist_dir = chroma_dir or CHROMA_DIR
    if not Path(persist_dir).exists():
        return {"ok": False, "error": f"ChromaDB directory not found: {persist_dir}"}

    client = chromadb.PersistentClient(path=persist_dir)

    try:
        client.delete_collection(collection_name)
    except Exception as exc:
        return {"ok": False, "error": f"Failed to delete collection: {exc}"}

    logger.info("🗑️  Deleted collection '%s'", collection_name)
    return {"ok": True, "collection": collection_name, "deleted": True}
