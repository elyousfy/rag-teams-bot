#!/usr/bin/env python3
"""
Document ingestion script for the RAG system.

Uses Docling for layout-aware document parsing with OCR and table extraction.
Supports: PDF, Word (.docx), PowerPoint (.pptx), HTML, Excel (.xlsx), Markdown, text, images.

Usage:
    python scripts/ingest.py [--clear]

Options:
    --clear     Clear existing collection before ingestion
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from llama_index.core import (
    StorageContext,
    VectorStoreIndex,
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.readers.docling import DoclingReader

from app import config

# File extensions Docling can handle
SUPPORTED_EXTENSIONS = [
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".html", ".md", ".txt",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
]


def setup_embedding_model():
    """Configure the embedding model."""
    return OllamaEmbedding(
        model_name=config.OLLAMA_EMBED_MODEL,
        base_url=config.OLLAMA_HOST,
    )


def find_documents(documents_path: Path) -> list[Path]:
    """Find all supported documents in the directory."""
    if not documents_path.exists():
        print(f"Creating documents directory: {documents_path}")
        documents_path.mkdir(parents=True, exist_ok=True)
        return []

    doc_files = []
    for ext in SUPPORTED_EXTENSIONS:
        doc_files.extend(documents_path.glob(f"**/*{ext}"))

    return sorted(doc_files)


def load_documents(file_paths: list[Path]) -> list:
    """Load documents using Docling's layout-aware parser."""
    # Docling exports as Markdown by default, preserving tables and structure
    reader = DoclingReader(export_type="markdown")

    str_paths = [str(p) for p in file_paths]
    documents = reader.load_data(file_path=str_paths)
    print(f"Loaded {len(documents)} document section(s) via Docling")

    return documents


def create_nodes(documents: list) -> list:
    """Split documents into chunks/nodes."""
    splitter = SentenceSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )

    nodes = splitter.get_nodes_from_documents(documents, show_progress=True)
    print(f"Created {len(nodes)} chunks")

    return nodes


def setup_vector_store(clear: bool = False) -> tuple:
    """Set up ChromaDB vector store. Returns (vector_store, existing_count)."""
    chroma_path = config.CHROMA_PATH
    chroma_path.mkdir(parents=True, exist_ok=True)

    chroma_client = chromadb.PersistentClient(path=str(chroma_path))

    collection_name = "company_docs"

    if clear:
        try:
            chroma_client.delete_collection(collection_name)
            print(f"Cleared existing collection: {collection_name}")
        except ValueError:
            pass

    chroma_collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    existing_count = chroma_collection.count()
    print(f"Collection '{collection_name}' has {existing_count} existing documents")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    return vector_store, existing_count


def ingest_documents(clear: bool = False):
    """Main ingestion pipeline."""
    print("=" * 60)
    print("RAG Document Ingestion (Docling)")
    print("=" * 60)

    # Setup embedding model
    print("\n1. Setting up embedding model...")
    embed_model = setup_embedding_model()
    Settings.embed_model = embed_model

    # Find documents
    print("\n2. Scanning for documents...")
    doc_files = find_documents(config.DOCUMENTS_PATH)

    if not doc_files:
        print(f"No documents found in {config.DOCUMENTS_PATH}")
        print(f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return

    print(f"Found {len(doc_files)} document(s):")
    for f in doc_files:
        print(f"  - {f.name}")

    # Load via Docling
    print("\n3. Parsing documents with Docling...")
    print("   (Layout analysis, OCR, and table extraction)")
    documents = load_documents(doc_files)

    if not documents:
        print("\nNo content extracted. Check that documents are not empty.")
        return

    # Chunk
    print("\n4. Chunking documents...")
    nodes = create_nodes(documents)

    # Setup vector store
    print("\n5. Setting up vector store...")
    vector_store, existing_count = setup_vector_store(clear=clear)

    # Warn about duplicates
    if existing_count > 0 and not clear:
        print("\n" + "!" * 60)
        print("WARNING: Collection already contains documents!")
        print("Running without --clear will ADD duplicates.")
        print("Use 'python scripts/ingest.py --clear' to replace existing data.")
        print("!" * 60)
        response = input("\nContinue anyway? [y/N]: ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return

    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Embed and store
    print("\n6. Creating embeddings and storing in ChromaDB...")
    print("   (This may take a while depending on document size)")

    VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
        show_progress=True,
    )

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print(f"Processed {len(doc_files)} file(s), {len(documents)} section(s)")
    print(f"Created {len(nodes)} chunks")
    print(f"Stored in: {config.CHROMA_PATH}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into the RAG system"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing collection before ingestion"
    )

    args = parser.parse_args()

    try:
        ingest_documents(clear=args.clear)
    except Exception as e:
        print(f"\nError during ingestion: {e}")
        raise


if __name__ == "__main__":
    main()
