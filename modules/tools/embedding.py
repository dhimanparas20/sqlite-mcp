"""ChromaDB embedding and vector store tools."""

from typing import Any, Dict

from langchain.tools import tool

from modules.embedder import (
    clear_collection,
    delete_collection,
    embed_and_store,
    list_collections,
    query_documents,
)
from modules.logger import get_logger

logger = get_logger(__name__)


@tool("embed_file")
def embed_file_tool(
    source: str,
    collection_name: str = "default",
) -> Dict[str, Any]:
    """Embed a file or URL into the local ChromaDB vector store.

    Supports PDF, Markdown, CSV, TXT, JSON, DOCX, HTML, XML files and web URLs.
    The file is loaded, chunked, embedded, and stored for later retrieval.

    Args:
        source: Path to a file or a URL to embed.
        collection_name: Name of the ChromaDB collection (default: "default").

    Returns:
        Dict containing:
            - ok: True if embedding succeeded
            - chunks: Number of text chunks stored
            - collection: ChromaDB collection name
            - error: Error message if failed
    """
    logger.info(f"[embed_file_tool] source: {source}, collection: {collection_name}")
    result = embed_and_store(source=source, collection_name=collection_name)
    logger.info(f"[embed_file_tool] result: {result}")
    return result


@tool("query_embedded_data")
def query_embedded_data_tool(
    query: str,
    collection_name: str = "default",
    k: int = 4,
) -> Dict[str, Any]:
    """Search embedded documents in ChromaDB using a text query.

    Retrieves the most relevant text chunks that were previously embedded
    via the embed_file tool. Returns matching content and metadata.

    Args:
        query: The search query string.
        collection_name: ChromaDB collection to search (default: "default").
        k: Number of results to return (default: 4).

    Returns:
        Dict containing:
            - ok: True if query succeeded
            - query: The original query
            - results: List of matching documents with content and metadata
            - error: Error message if failed
    """
    logger.info(f"[query_embedded_data_tool] query: {query}, collection: {collection_name}, k: {k}")
    result = query_documents(query=query, collection_name=collection_name, k=k)
    logger.info(f"[query_embedded_data_tool] found {len(result.get('results', []))} results")
    return result


@tool("list_chroma_collections")
def list_chroma_collections_tool() -> Dict[str, Any]:
    """List all ChromaDB vector store collections and their document counts.

    Returns:
        Dict containing:
            - ok: True if listing succeeded
            - collections: List of collections with name and count
            - count: Total number of collections
    """
    result = list_collections()
    logger.info(f"[list_chroma_collections_tool] found {result.get('count', 0)} collections")
    return result


@tool("clear_chroma_collection")
def clear_chroma_collection_tool(
    collection_name: str = "default",
) -> Dict[str, Any]:
    """Delete all documents from a ChromaDB collection without removing the collection itself.

    Use this to clear embedded data from a collection while keeping the collection structure.

    Args:
        collection_name: Name of the collection to clear (default: "default").

    Returns:
        Dict containing:
            - ok: True if clearing succeeded
            - collection: Name of the cleared collection
            - deleted: Number of items deleted
    """
    logger.info(f"[clear_chroma_collection_tool] collection: {collection_name}")
    result = clear_collection(collection_name=collection_name)
    logger.info(f"[clear_chroma_collection_tool] result: {result}")
    return result


@tool("delete_chroma_collection")
def delete_chroma_collection_tool(
    collection_name: str = "default",
) -> Dict[str, Any]:
    """Delete an entire ChromaDB collection and all its embedded documents.

    This permanently removes the collection and all data inside it.

    Args:
        collection_name: Name of the collection to delete (default: "default").

    Returns:
        Dict containing:
            - ok: True if deletion succeeded
            - collection: Name of the deleted collection
            - deleted: True if deleted
    """
    logger.info(f"[delete_chroma_collection_tool] collection: {collection_name}")
    result = delete_collection(collection_name=collection_name)
    logger.info(f"[delete_chroma_collection_tool] result: {result}")
    return result
